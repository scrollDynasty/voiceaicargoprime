/**
 * RingCentral WebPhone Bridge
 * Автоматически принимает входящие звонки и передает их в Python Voice AI систему
 */

require('dotenv').config();
const SDK = require('@ringcentral/sdk').SDK;
const WebPhone = require('ringcentral-web-phone').default;
const axios = require('axios');
const WebSocket = require('ws');
const winston = require('winston');
const { v4: uuidv4 } = require('uuid');
const express = require('express');

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
        new winston.transports.File({ filename: 'webphone-bridge.log' })
    ]
});

// Конфигурация
const config = {
    clientId: process.env.RINGCENTRAL_CLIENT_ID,
    clientSecret: process.env.RINGCENTRAL_CLIENT_SECRET,
    jwtToken: process.env.RINGCENTRAL_JWT_TOKEN,
    server: process.env.RINGCENTRAL_SERVER || 'https://platform.ringcentral.com',
    pythonServer: process.env.PYTHON_AI_SERVER || 'http://localhost:5000',
    pythonEndpoint: process.env.PYTHON_AI_ENDPOINT || '/api/handle-webphone-call',
    wsPort: parseInt(process.env.WEBSOCKET_PORT || '8080'),
    audioSampleRate: parseInt(process.env.AUDIO_SAMPLE_RATE || '16000'),
    audioChannels: parseInt(process.env.AUDIO_CHANNELS || '1')
};

// Глобальные переменные
let rcsdk = null;
let webPhone = null;
let platform = null;
let activeCalls = new Map();
let wsServer = null;

/**
 * Инициализация RingCentral SDK
 */
async function initializeRingCentral() {
    logger.info('🚀 Инициализация RingCentral SDK...');
    
    try {
        // Создаем SDK
        rcsdk = new SDK({
            clientId: config.clientId,
            clientSecret: config.clientSecret,
            server: config.server
        });
        
        platform = rcsdk.platform();
        
        // Авторизация через JWT
        logger.info('🔐 Авторизация через JWT токен...');
        await platform.login({
            jwt: config.jwtToken
        });
        
        logger.info('✅ RingCentral SDK успешно инициализирован');
        
        // Получаем информацию о расширении
        const extensionInfo = await platform.get('/restapi/v1.0/account/~/extension/~');
        const extension = await extensionInfo.json();
        logger.info(`📞 Расширение: ${extension.extensionNumber}`);
        logger.info(`👤 Пользователь: ${extension.name}`);
        
        return true;
    } catch (error) {
        logger.error(`❌ Ошибка инициализации RingCentral: ${error.message}`);
        return false;
    }
}

/**
 * Инициализация WebPhone
 */
async function initializeWebPhone() {
    logger.info('📞 Инициализация WebPhone...');
    
    try {
        // Создаем WebPhone инстанс
        webPhone = new WebPhone({
            logLevel: 1, // 0 = Trace, 1 = Debug, 2 = Info, 3 = Warn, 4 = Error
            audioHelper: {
                enabled: true,
                incoming: 'audio/incoming.ogg', // Звук входящего звонка
                outgoing: 'audio/outgoing.ogg'  // Звук исходящего звонка
            },
            media: {
                remote: {
                    audio: true,
                    video: false
                },
                local: {
                    audio: true,
                    video: false
                }
            },
            enableDscp: true,
            enableQos: true,
            sipInfo: await getSipProvisionData()
        });
        
        // Регистрация обработчиков событий
        setupWebPhoneEventHandlers();
        
        logger.info('✅ WebPhone успешно инициализирован');
        return true;
    } catch (error) {
        logger.error(`❌ Ошибка инициализации WebPhone: ${error.message}`);
        return false;
    }
}

/**
 * Получение SIP данных для WebPhone
 */
async function getSipProvisionData() {
    try {
        const response = await platform.post('/restapi/v1.0/client-info/sip-provision', {
            sipInfo: [{
                transport: 'WSS'
            }]
        });
        
        const data = await response.json();
        return data.sipInfo[0];
    } catch (error) {
        logger.error(`❌ Ошибка получения SIP данных: ${error.message}`);
        throw error;
    }
}

/**
 * Настройка обработчиков событий WebPhone
 */
function setupWebPhoneEventHandlers() {
    // Событие регистрации
    webPhone.on('registered', () => {
        logger.info('✅ WebPhone зарегистрирован и готов принимать звонки');
    });
    
    // Событие ошибки регистрации
    webPhone.on('registrationFailed', (error) => {
        logger.error(`❌ Ошибка регистрации WebPhone: ${error.message}`);
    });
    
    // КРИТИЧНО: Обработчик входящих звонков
    webPhone.on('invite', async (session) => {
        logger.info('🔔 ВХОДЯЩИЙ ЗВОНОК ОБНАРУЖЕН!');
        
        const callId = uuidv4();
        const fromNumber = session.request.from.displayName || session.request.from.uri.user || 'Unknown';
        const toNumber = session.request.to.displayName || session.request.to.uri.user || 'Unknown';
        
        logger.info(`📞 Звонок от: ${fromNumber}`);
        logger.info(`📞 Звонок на: ${toNumber}`);
        logger.info(`🆔 ID звонка: ${callId}`);
        
        // Сохраняем информацию о звонке
        const callData = {
            callId,
            sessionId: session.id,
            from: fromNumber,
            to: toNumber,
            startTime: new Date(),
            session: session,
            audioStream: null,
            wsConnection: null
        };
        
        activeCalls.set(callId, callData);
        
        try {
            // АВТОМАТИЧЕСКИ ПРИНИМАЕМ ЗВОНОК
            logger.info('🤖 Автоматически принимаем звонок...');
            await session.accept();
            logger.info('✅ Звонок принят!');
            
            // Настраиваем обработчики для сессии
            setupSessionHandlers(session, callId);
            
            // Уведомляем Python сервер о новом звонке
            await notifyPythonServer(callData);
            
            // Начинаем обработку аудио
            startAudioProcessing(session, callId);
            
        } catch (error) {
            logger.error(`❌ Ошибка при приеме звонка: ${error.message}`);
            activeCalls.delete(callId);
        }
    });
}

/**
 * Настройка обработчиков для конкретной сессии звонка
 */
function setupSessionHandlers(session, callId) {
    // Звонок установлен
    session.on('accepted', () => {
        logger.info(`✅ Звонок ${callId} успешно установлен`);
    });
    
    // Звонок завершен
    session.on('terminated', () => {
        logger.info(`📞 Звонок ${callId} завершен`);
        cleanupCall(callId);
    });
    
    // Ошибка в звонке
    session.on('failed', (error) => {
        logger.error(`❌ Ошибка в звонке ${callId}: ${error}`);
        cleanupCall(callId);
    });
    
    // Получение DTMF (тоновый набор)
    session.on('dtmf', (request, dtmf) => {
        logger.info(`📱 DTMF получен для звонка ${callId}: ${dtmf}`);
        // Можно передать в Python для обработки
    });
}

/**
 * Уведомление Python сервера о новом звонке
 */
async function notifyPythonServer(callData) {
    try {
        const payload = {
            callId: callData.callId,
            sessionId: callData.sessionId,
            from: callData.from,
            to: callData.to,
            timestamp: callData.startTime,
            source: 'webphone'
        };
        
        logger.info(`📤 Отправка данных звонка в Python: ${config.pythonServer}${config.pythonEndpoint}`);
        
        const response = await axios.post(
            `${config.pythonServer}${config.pythonEndpoint}`,
            payload,
            {
                headers: {
                    'Content-Type': 'application/json'
                },
                timeout: 5000
            }
        );
        
        logger.info(`✅ Python сервер ответил: ${response.status}`);
        
    } catch (error) {
        logger.error(`❌ Ошибка отправки в Python: ${error.message}`);
    }
}

/**
 * Начало обработки аудио потока
 */
function startAudioProcessing(session, callId) {
    logger.info(`🎤 Начинаем обработку аудио для звонка ${callId}`);
    
    const callData = activeCalls.get(callId);
    if (!callData) return;
    
    // Получаем медиа потоки
    const localStream = session.localMediaStream;
    const remoteStream = session.remoteMediaStream;
    
    if (remoteStream) {
        logger.info(`🎧 Удаленный аудио поток доступен`);
        
        // Создаем WebSocket соединение для стриминга аудио в Python
        const ws = new WebSocket(`ws://localhost:${config.wsPort}/audio/${callId}`);
        
        ws.on('open', () => {
            logger.info(`🔌 WebSocket соединение установлено для звонка ${callId}`);
            callData.wsConnection = ws;
            
            // Начинаем стриминг аудио
            streamAudioToPython(remoteStream, ws, callId);
        });
        
        ws.on('message', (data) => {
            // Получаем синтезированное аудио от Python
            handlePythonAudioResponse(data, session, callId);
        });
        
        ws.on('error', (error) => {
            logger.error(`❌ WebSocket ошибка для звонка ${callId}: ${error.message}`);
        });
        
        ws.on('close', () => {
            logger.info(`🔌 WebSocket закрыт для звонка ${callId}`);
        });
    }
}

/**
 * Стриминг аудио в Python через WebSocket
 */
function streamAudioToPython(mediaStream, ws, callId) {
    // Здесь должна быть реализация захвата аудио из mediaStream
    // и отправка его через WebSocket
    // Это требует использования Web Audio API или других методов
    
    logger.info(`🎤 Стриминг аудио начат для звонка ${callId}`);
    
    // Заглушка: отправляем тестовые данные
    const interval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
            // В реальной реализации здесь должны быть реальные аудио данные
            const audioChunk = Buffer.alloc(1024); // Заглушка
            ws.send(audioChunk);
        } else {
            clearInterval(interval);
        }
    }, 100);
    
    activeCalls.get(callId).audioStreamInterval = interval;
}

/**
 * Обработка аудио ответа от Python
 */
function handlePythonAudioResponse(audioData, session, callId) {
    try {
        logger.info(`🔊 Получено аудио от Python для звонка ${callId}: ${audioData.length} байт`);
        
        // Здесь должна быть реализация воспроизведения аудио в звонке
        // Это требует использования WebRTC API для вставки аудио в поток
        
        // Заглушка
        logger.info(`🔊 Воспроизведение аудио в звонке ${callId}`);
        
    } catch (error) {
        logger.error(`❌ Ошибка воспроизведения аудио: ${error.message}`);
    }
}

/**
 * Очистка ресурсов после завершения звонка
 */
function cleanupCall(callId) {
    const callData = activeCalls.get(callId);
    if (!callData) return;
    
    logger.info(`🧹 Очистка ресурсов для звонка ${callId}`);
    
    // Закрываем WebSocket
    if (callData.wsConnection) {
        callData.wsConnection.close();
    }
    
    // Останавливаем аудио стриминг
    if (callData.audioStreamInterval) {
        clearInterval(callData.audioStreamInterval);
    }
    
    // Удаляем из активных звонков
    activeCalls.delete(callId);
    
    logger.info(`✅ Ресурсы очищены для звонка ${callId}`);
}

/**
 * Инициализация WebSocket сервера для аудио стриминга
 */
function initializeWebSocketServer() {
    const app = express();
    const server = require('http').createServer(app);
    
    wsServer = new WebSocket.Server({ server });
    
    wsServer.on('connection', (ws, req) => {
        const callId = req.url.split('/').pop();
        logger.info(`🔌 Новое WebSocket соединение для звонка ${callId}`);
        
        ws.on('error', (error) => {
            logger.error(`❌ WebSocket ошибка: ${error.message}`);
        });
    });
    
    server.listen(config.wsPort, () => {
        logger.info(`🌐 WebSocket сервер запущен на порту ${config.wsPort}`);
    });
}

/**
 * Главная функция запуска
 */
async function main() {
    logger.info('🎯 Запуск RingCentral WebPhone Bridge...');
    logger.info('📋 Конфигурация:');
    logger.info(`   Client ID: ${config.clientId.substring(0, 10)}...`);
    logger.info(`   Server: ${config.server}`);
    logger.info(`   Python Server: ${config.pythonServer}`);
    
    // Инициализация компонентов
    const rcInitialized = await initializeRingCentral();
    if (!rcInitialized) {
        logger.error('❌ Не удалось инициализировать RingCentral SDK');
        process.exit(1);
    }
    
    const wpInitialized = await initializeWebPhone();
    if (!wpInitialized) {
        logger.error('❌ Не удалось инициализировать WebPhone');
        process.exit(1);
    }
    
    // Запуск WebSocket сервера
    initializeWebSocketServer();
    
    logger.info('✅ WebPhone Bridge успешно запущен и готов принимать звонки!');
    logger.info('🎯 Ожидание входящих звонков...');
    
    // Обработка завершения процесса
    process.on('SIGINT', () => {
        logger.info('🛑 Получен сигнал завершения...');
        shutdown();
    });
    
    process.on('SIGTERM', () => {
        logger.info('🛑 Получен сигнал завершения...');
        shutdown();
    });
}

/**
 * Корректное завершение работы
 */
function shutdown() {
    logger.info('🛑 Завершение работы WebPhone Bridge...');
    
    // Завершаем все активные звонки
    activeCalls.forEach((callData, callId) => {
        logger.info(`📞 Завершение звонка ${callId}`);
        if (callData.session) {
            callData.session.terminate();
        }
        cleanupCall(callId);
    });
    
    // Закрываем WebSocket сервер
    if (wsServer) {
        wsServer.close();
    }
    
    // Выход из программы
    process.exit(0);
}

// Запуск приложения
main().catch(error => {
    logger.error(`💥 Критическая ошибка: ${error.message}`);
    process.exit(1);
});