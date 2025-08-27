/**
 * RingCentral WebPhone Bridge with Puppeteer
 * Uses real browser with WebRTC support
 */

require('dotenv').config();
const puppeteer = require('puppeteer');
const express = require('express');
const WebSocket = require('ws');
const winston = require('winston');
const axios = require('axios');
const path = require('path');
const fs = require('fs');

// Настройка логирования
const logger = winston.createLogger({
    level: process.env.LOG_LEVEL || 'info',
    format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.printf(({ timestamp, level, message }) => {
            return `${timestamp} [${level.toUpperCase()}] ${message}`;
        })
    ),
    transports: [
        new winston.transports.Console(),
        new winston.transports.File({ filename: 'webphone-puppeteer.log' })
    ]
});

// Конфигурация
const config = {
    clientId: process.env.RINGCENTRAL_CLIENT_ID || 'bXCZ510zNmybxAUXGIZruT',
    clientSecret: process.env.RINGCENTRAL_CLIENT_SECRET || '10hW9ccNfhyc1y69bQzdgnVUnFyf76B6qcmwOtypEGo7',
    jwtToken: process.env.RINGCENTRAL_JWT_TOKEN || 'eyJraWQiOiI4NzYyZjU5OGQwNTk0NGRiODZiZjVjYTk3ODA0NzYwOCIsInR5cCI6IkpXVCIsImFsZyI6IlJTMjU2In0.eyJhdWQiOiJodHRwczovL3BsYXRmb3JtLnJpbmdjZW50cmFsLmNvbS9yZXN0YXBpL29hdXRoL3Rva2VuIiwic3ViIjoiMjA2OTkwOTAxOSIsImlzcyI6Imh0dHBzOi8vcGxhdGZvcm0ucmluZ2NlbnRyYWwuY29tIiwiZXhwIjozOTAzNjUxMzQyLCJpYXQiOjE3NTYxNjc2OTUsImp0aSI6IlpTckJuOHlFVDJLeEFjOXhmTlZ6ZncifQ.fHF6mXLa9wHygLYiFVQzIo4bKT8niwnYKD7PT7gFGoayZpDOkHwamesmXunn_IIY3rRT9Z2hXHgaJpdpW5ZRimaYOydcjGpj1HgdOxmTRBcYj6B4HWXb9YXO95Q2sfFLPS-3DwvcxeqNW8yoX3Cx31VpCfsybrvwq1NtDO73KulJYPByTSjoLQMj5to5gxRtKlqbhabj1o4YaeKkKb70_Sr-T0lXQS_93fOaPi0xP_AYNhDmDEQBZc1tvwUF7-ETj2Bv-EnfH5OxWfbRS3bSnZdRs1P-0TJg6SfNgwlAGNnMqEdpVyBMXt-02aQA8xgo1O9RDI-nSUXd2iKaA5CTAg',
    server: process.env.RINGCENTRAL_SERVER || 'https://platform.ringcentral.com',
    pythonServer: process.env.PYTHON_AI_SERVER || 'http://localhost:5000',
    wsPort: 8082, // WebSocket port for browser communication
    webhookPort: 8081, // Port for webhook events from Python
    headless: process.env.HEADLESS !== 'false', // Run in headless mode by default
};

// Глобальные переменные
let browser = null;
let page = null;
let wsServer = null;
let webhookWsServer = null;
let browserWsConnection = null;
let activeCalls = new Map();
let audioBuffer = [];

// Запуск Express сервера для обслуживания HTML файлов
function startHTTPServer() {
    const app = express();
    app.use(express.static(path.join(__dirname)));
    
    const server = app.listen(0, () => {
        const port = server.address().port;
        logger.info(`📁 HTTP server started on port ${port}`);
        return port;
    });
    
    return server;
}

// Запуск WebSocket сервера для связи с браузером
function startWebSocketServer() {
    wsServer = new WebSocket.Server({ port: config.wsPort });
    
    wsServer.on('connection', (ws) => {
        logger.info('✅ Browser WebSocket connected');
        browserWsConnection = ws;
        
        ws.on('message', (message) => {
            try {
                // Check if message is binary (audio data)
                if (message instanceof Buffer) {
                    handleAudioData(message);
                } else {
                    const data = JSON.parse(message);
                    handleBrowserMessage(data);
                }
            } catch (error) {
                logger.error(`❌ Failed to process browser message: ${error.message}`);
            }
        });
        
        ws.on('close', () => {
            logger.warn('⚠️ Browser WebSocket disconnected');
            browserWsConnection = null;
        });
        
        ws.on('error', (error) => {
            logger.error(`❌ Browser WebSocket error: ${error.message}`);
        });
    });
    
    logger.info(`🌐 WebSocket server for browser started on port ${config.wsPort}`);
}

// Запуск WebSocket сервера для webhook событий от Python
function startWebhookServer() {
    webhookWsServer = new WebSocket.Server({ port: config.webhookPort });
    
    webhookWsServer.on('connection', (ws) => {
        logger.info('✅ Python webhook WebSocket connected');
        
        ws.on('message', (message) => {
            try {
                const data = JSON.parse(message);
                handleWebhookEvent(data);
            } catch (error) {
                logger.error(`❌ Failed to process webhook: ${error.message}`);
            }
        });
    });
    
    logger.info(`🌐 WebSocket server for webhooks started on port ${config.webhookPort}`);
}

// Обработка сообщений от браузера
function handleBrowserMessage(data) {
    switch (data.type) {
        case 'log':
            logger.info(`[Browser] ${data.message}`, data.data || {});
            break;
            
        case 'status':
            logger.info(`📊 WebPhone status: ${data.status}`);
            break;
            
        case 'incomingCall':
            logger.info(`📞 Incoming call from ${data.from} to ${data.to}`);
            activeCalls.set(data.sessionId, {
                sessionId: data.sessionId,
                from: data.from,
                to: data.to,
                startTime: Date.now()
            });
            // Уведомить Python сервер о входящем звонке
            notifyPythonServer('incoming_call', data);
            break;
            
        case 'callEnded':
            logger.info(`📞 Call ended: ${data.sessionId}`);
            activeCalls.delete(data.sessionId);
            // Уведомить Python сервер о завершении звонка
            notifyPythonServer('call_ended', data);
            // Очистить аудио буфер
            audioBuffer = [];
            break;
            
        default:
            logger.warn(`Unknown message type from browser: ${data.type}`);
    }
}

// Обработка аудио данных от браузера
function handleAudioData(audioData) {
    // Добавить в буфер
    audioBuffer.push(audioData);
    
    // Отправить аудио в Python сервер когда накопится достаточно данных
    if (audioBuffer.length >= 10) { // ~160ms при 16kHz
        sendAudioToPython();
    }
}

// Отправка аудио в Python сервер
async function sendAudioToPython() {
    if (audioBuffer.length === 0) return;
    
    try {
        // Объединить все аудио фрагменты
        const combinedBuffer = Buffer.concat(audioBuffer);
        audioBuffer = []; // Очистить буфер
        
        // Отправить в Python сервер
        const response = await axios.post(
            `${config.pythonServer}/api/process-audio`,
            combinedBuffer,
            {
                headers: {
                    'Content-Type': 'audio/raw',
                    'X-Sample-Rate': '16000',
                    'X-Channels': '1',
                    'X-Encoding': 'pcm16'
                }
            }
        );
        
        if (response.data && response.data.response_audio) {
            // TODO: Отправить ответное аудио обратно в браузер для воспроизведения
            logger.info('🎵 Received response audio from Python');
        }
        
    } catch (error) {
        logger.error(`❌ Failed to send audio to Python: ${error.message}`);
    }
}

// Уведомление Python сервера о событиях
async function notifyPythonServer(event, data) {
    try {
        await axios.post(
            `${config.pythonServer}/api/webphone-event`,
            {
                event,
                data,
                timestamp: new Date().toISOString()
            }
        );
    } catch (error) {
        logger.error(`❌ Failed to notify Python server: ${error.message}`);
    }
}

// Обработка webhook событий от Python
function handleWebhookEvent(data) {
    logger.info(`📨 Webhook event from Python: ${data.event || data.uuid}`);
    
    // Пересылаем событие в браузер если нужно
    if (browserWsConnection && browserWsConnection.readyState === WebSocket.OPEN) {
        browserWsConnection.send(JSON.stringify({
            type: 'webhook',
            data
        }));
    }
}

// Запуск Puppeteer браузера
async function launchBrowser() {
    logger.info('🚀 Launching Puppeteer browser...');
    
    try {
        browser = await puppeteer.launch({
            headless: config.headless ? 'new' : false,
            args: [
                '--use-fake-ui-for-media-stream',
                '--use-fake-device-for-media-stream',
                '--allow-file-access',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--autoplay-policy=no-user-gesture-required'
            ]
        });
        
        page = await browser.newPage();
        
        // Включить консольные логи
        page.on('console', msg => {
            const type = msg.type();
            const text = msg.text();
            if (type === 'error') {
                logger.error(`[Browser Console] ${text}`);
            } else {
                logger.info(`[Browser Console] ${text}`);
            }
        });
        
        // Обработка ошибок страницы
        page.on('pageerror', error => {
            logger.error(`[Browser Error] ${error.message}`);
        });
        
        // Разрешить доступ к микрофону
        const context = browser.defaultBrowserContext();
        await context.overridePermissions('http://localhost', ['microphone']);
        
        logger.info('✅ Browser launched successfully');
        
    } catch (error) {
        logger.error(`❌ Failed to launch browser: ${error.message}`);
        throw error;
    }
}

// Загрузка WebPhone в браузере
async function loadWebPhone(httpPort) {
    logger.info('📄 Loading WebPhone page...');
    
    try {
        // Загрузить HTML страницу
        await page.goto(`http://localhost:${httpPort}/webphone.html`, {
            waitUntil: 'networkidle0'
        });
        
        // Инжектировать конфигурацию
        await page.evaluate((config) => {
            window.RINGCENTRAL_CONFIG = {
                clientId: config.clientId,
                clientSecret: config.clientSecret,
                jwtToken: config.jwtToken,
                server: config.server
            };
        }, config);
        
        logger.info('✅ WebPhone page loaded and configured');
        
        // Ждать инициализации WebPhone
        await page.waitForFunction(
            () => document.getElementById('status').textContent.includes('Ready') || 
                 document.getElementById('status').textContent.includes('Registered'),
            { timeout: 30000 }
        );
        
        logger.info('✅ WebPhone initialized and ready');
        
    } catch (error) {
        logger.error(`❌ Failed to load WebPhone: ${error.message}`);
        
        // Сделать скриншот для отладки
        if (page) {
            await page.screenshot({ path: 'webphone-error.png' });
            logger.info('📸 Screenshot saved to webphone-error.png');
        }
        
        throw error;
    }
}

// Основная функция запуска
async function main() {
    logger.info('🎯 Starting RingCentral WebPhone Bridge with Puppeteer...');
    logger.info('📋 Configuration:');
    logger.info(`   Client ID: ${config.clientId.substring(0, 10)}...`);
    logger.info(`   Server: ${config.server}`);
    logger.info(`   Python Server: ${config.pythonServer}`);
    logger.info(`   Headless: ${config.headless}`);
    
    try {
        // Запустить HTTP сервер
        const httpServer = startHTTPServer();
        const httpPort = httpServer.address().port;
        
        // Запустить WebSocket серверы
        startWebSocketServer();
        startWebhookServer();
        
        // Запустить браузер
        await launchBrowser();
        
        // Загрузить WebPhone
        await loadWebPhone(httpPort);
        
        logger.info('✅ WebPhone Bridge with Puppeteer started successfully!');
        logger.info('🎯 Waiting for incoming calls...');
        
        // Проверка здоровья
        setInterval(async () => {
            if (page && !page.isClosed()) {
                const status = await page.evaluate(() => {
                    return document.getElementById('status').textContent;
                });
                logger.info(`🩺 Health check - Status: ${status}, Active calls: ${activeCalls.size}`);
            }
        }, 30000);
        
    } catch (error) {
        logger.error(`❌ Failed to start WebPhone Bridge: ${error.message}`);
        await cleanup();
        process.exit(1);
    }
}

// Очистка ресурсов
async function cleanup() {
    logger.info('🧹 Cleaning up...');
    
    if (browser) {
        await browser.close();
    }
    
    if (wsServer) {
        wsServer.close();
    }
    
    if (webhookWsServer) {
        webhookWsServer.close();
    }
}

// Обработка сигналов завершения
process.on('SIGINT', async () => {
    logger.info('🛑 SIGINT received, shutting down...');
    await cleanup();
    process.exit(0);
});

process.on('SIGTERM', async () => {
    logger.info('🛑 SIGTERM received, shutting down...');
    await cleanup();
    process.exit(0);
});

// Запуск
main().catch(async (error) => {
    logger.error(`❌ Fatal error: ${error.message}`);
    await cleanup();
    process.exit(1);
});