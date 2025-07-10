// wa_bridge.js

// --- Dependencies ---
const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const winston = require('winston');

// --- Configuration ---
const FASTAPI_BASE_URL = process.env.FASTAPI_BASE_URL || 'http://localhost:8001';
const FAST_POLLING_INTERVAL_MS = 1500; // Poll quickly when connected
const SLOW_POLLING_INTERVAL_MS = 10000; // Poll slowly when backend is down
const MAX_SEND_RETRIES = 3;
const SEND_RETRY_DELAY_MS = 2000;
const MAX_ACK_RETRIES = 3;
const ACK_RETRY_DELAY_MS = 3000;
const FAILED_ACK_QUARANTINE_CLEAR_MS = 3600000; // 1 hour
const RESTART_INTERVAL_MS = 21600000; // Periodically restart every 6 hours

// --- Winston Logger ---
const logger = winston.createLogger({
  level: 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.printf(({ timestamp, level, message }) => `${timestamp} [${level.toUpperCase()}] [wa_bridge] ${message}`)
  ),
  transports: [
    new winston.transports.Console(),
    new winston.transports.File({ filename: 'logs/kairo_wa_bridge_error.log', level: 'error' }),
    new winston.transports.File({ filename: 'logs/kairo_wa_bridge_combined.log' }),
  ],
});

// --- State Variables ---
let isClientReady = false;
let clientInstance;
let _stopPollingFlag = false;
const failedAckStore = new Set();
let isBackendConnected = true; // Assume backend is up at the start

// Periodically clear the ACK quarantine to give messages another chance
setInterval(() => {
    if (failedAckStore.size > 0) {
        logger.info(`Clearing ACK failure quarantine. ${failedAckStore.size} items are now retryable.`);
        failedAckStore.clear();
    }
}, FAILED_ACK_QUARANTINE_CLEAR_MS);

// Periodically restart the script for long-term stability
setTimeout(() => {
    logger.warn('Initiating scheduled periodic restart for stability.');
    shutdownBridge('PERIODIC_RESTART');
}, RESTART_INTERVAL_MS);


// --- Utility: Sleep Function ---
function sleep(ms) { return new Promise(resolve => setTimeout(resolve, ms)); }

// --- Initialize the WhatsApp client ---
const client = new Client({
    authStrategy: new LocalAuth({ dataPath: '.wwebjs_auth' }),
    puppeteer: {
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
    }
});
clientInstance = client;

// --- Event Handlers ---
client.on('qr', qr => { qrcode.generate(qr, { small: true }); });
client.on('ready', () => {
    logger.info('WhatsApp client is ready!');
    isClientReady = true;
    pollForOutgoingMessages();
});
client.on('auth_failure', msg => {
    logger.error(`AUTHENTICATION FAILURE: ${msg}. Shutting down.`);
    shutdownBridge('AUTH_FAILURE', 1);
});
client.on('disconnected', reason => {
    logger.error(`Client disconnected: ${reason}. Shutting down.`);
    shutdownBridge('DISCONNECTED', 1);
});
client.on('error', err => {
    logger.error(`Unhandled WhatsApp client error: ${err.message}`);
});

client.on('message', async (message) => {
    const chat = await message.getChat();
    if (message.isStatus || chat.isGroup) return; // Ignore status updates and group chats

    logger.info(`Received message from ${message.from}: "${message.body.substring(0, 50)}..."`);
    try {
        await axios.post(`${FASTAPI_BASE_URL}/incoming`, {
            user_id: message.from,
            message: message.body
        }, { timeout: 10000 });
    } catch (error) {
        logger.error(`Failed to send incoming message to backend: ${error.message}`);
    }
});

// --- Main Polling Function ---
async function pollForOutgoingMessages() {
    if (_stopPollingFlag) return;
    if (!isClientReady) {
        setTimeout(pollForOutgoingMessages, 5000); // Wait if client isn't ready
        return;
    }

    try {
        const response = await axios.get(`${FASTAPI_BASE_URL}/outgoing`, { timeout: 5000 });
        
        if (!isBackendConnected) {
            logger.info('Connection to Kairo backend RESTORED. Resuming normal polling.');
            isBackendConnected = true;
        }

        const messages = response.data.messages;
        if (messages && messages.length > 0) {
            for (const msg of messages) {
                if (failedAckStore.has(msg.message_id)) continue;

                let sentSuccessfully = false;
                for (let attempt = 1; attempt <= MAX_SEND_RETRIES; attempt++) {
                    try {
                        await client.sendMessage(msg.user_id, msg.message);
                        sentSuccessfully = true;
                        logger.info(`Message sent to ${msg.user_id} (ID: ${msg.message_id})`);
                        break;
                    } catch (sendError) {
                        logger.error(`Send attempt ${attempt} failed for ID ${msg.message_id}: ${sendError.message}`);
                        if (attempt < MAX_SEND_RETRIES) await sleep(SEND_RETRY_DELAY_MS);
                    }
                }

                if (sentSuccessfully) {
                    let ackSentSuccessfully = false;
                    for (let ackAttempt = 1; ackAttempt <= MAX_ACK_RETRIES; ackAttempt++) {
                        try {
                            await axios.post(`${FASTAPI_BASE_URL}/ack`, { message_id: msg.message_id }, { timeout: 3000 });
                            ackSentSuccessfully = true;
                            break;
                        } catch (ackError) {
                            logger.error(`ACK attempt ${ackAttempt} failed for ID ${msg.message_id}: ${ackError.message}`);
                            if (ackAttempt < MAX_ACK_RETRIES) await sleep(ACK_RETRY_DELAY_MS);
                        }
                    }

                    if (!ackSentSuccessfully) {
                        logger.error(`All ACK attempts failed for message ID: ${msg.message_id}. Quarantining.`);
                        failedAckStore.add(msg.message_id);
                    }
                }
            }
        }
    } catch (error) {
        if (isBackendConnected) {
            let detail = (error.code) ? `(${error.code})` : `(${error.message})`;
            logger.error(`Connection to Kairo backend LOST. Is the Python server running? ${detail}. Switching to slow poll mode.`);
            isBackendConnected = false;
        }
    } finally {
        if (!_stopPollingFlag) {
            const nextPollDelay = isBackendConnected ? FAST_POLLING_INTERVAL_MS : SLOW_POLLING_INTERVAL_MS;
            setTimeout(pollForOutgoingMessages, nextPollDelay);
        }
    }
}

// --- Shutdown and Initialization ---
async function shutdownBridge(signal, exitCode = 0) {
    if (_stopPollingFlag) return;
    _stopPollingFlag = true;
    logger.warn(`Received ${signal}, initiating graceful shutdown...`);
    if (clientInstance) {
        try {
            await clientInstance.destroy();
            logger.info('WhatsApp client destroyed.');
        } catch (e) {
            logger.error(`Error destroying client during shutdown: ${e.message}`);
        }
    }
    logger.warn('Bridge shutdown complete.');
    process.exit(exitCode);
}

process.on('SIGINT', () => shutdownBridge('SIGINT'));
process.on('SIGTERM', () => shutdownBridge('SIGTERM'));

client.initialize().catch(err => {
    logger.error(`CRITICAL: Client initialization failed: ${err.message}. Exiting.`);
    process.exit(1);
});