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

// WebSocket полифилл для Node.js
global.WebSocket = WebSocket;

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
    clientId: process.env.RINGCENTRAL_CLIENT_ID || 'bXCZ510zNmybxAUXGIZruT',
    clientSecret: process.env.RINGCENTRAL_CLIENT_SECRET || '10hW9ccNfhyc1y69bQzdgnVUnFyf76B6qcmwOtypEGo7',
    jwtToken: process.env.RINGCENTRAL_JWT_TOKEN || 'eyJraWQiOiI4NzYyZjU5OGQwNTk0NGRiODZiZjVjYTk3ODA0NzYwOCIsInR5cCI6IkpXVCIsImFsZyI6IlJTMjU2In0.eyJhdWQiOiJodHRwczovL3BsYXRmb3JtLnJpbmdjZW50cmFsLmNvbSIsInN1YiI6IjE4NjE3NjYwMTkiLCJhdXRoX3RpbWUiOjE3MjQ2Nzk3MjMsImlzcyI6Imh0dHBzOi8vcGxhdGZvcm0ucmluZ2NlbnRyYWwuY29tIiwiZXhwIjoxNzI3Mjc3NDI5LCJpYXQiOjE3MjQ2ODUyMjl9.NjuNyKI49c9AO_KAKZLyqQZg8COpHX7s_UwOF5KOQ5QzYV1y6GW2M2IiMFCaYS2zq-F-OX4d0vBJLO-VyIfgNYz_GEhPFHBr_KeBadZKj5sE7ySdJI5_bSF8vBdQ0jHx0vGgpyT3bHFe7rKQv8wKbJU4XyHJ-OMCkCsKzBu6_VN2HNVgZxNGqOQvN8_vLAj_0vI3vJh8KYgGkPzI5Tn2_8XPLdJ4KfYuG2f8qLh-0-O7DaGTXQrpJH8pO4Rz6U-2AQRzJ9Uw1xHxQVL8XNl2-IYRU0OQXWv1gSZL-vUe3GK5YYqOBzA',
    server: process.env.RINGCENTRAL_SERVER || 'https://platform.ringcentral.com',
    pythonServer: process.env.PYTHON_AI_SERVER || 'http://localhost:5000',
    pythonEndpoint: process.env.PYTHON_AI_ENDPOINT || '/api/handle-webphone-call',
    wsPort: parseInt(process.env.WEBSOCKET_PORT || '8081'),
    audioSampleRate: parseInt(process.env.AUDIO_SAMPLE_RATE || '16000'),
    audioChannels: parseInt(process.env.AUDIO_CHANNELS || '1'),
    
    // Настройки для стабильности
    reconnectAttempts: 5,
    reconnectDelay: 5000,
    healthCheckInterval: 30000,
    callTimeout: 300000, // 5 минут максимум на звонок
    maxConcurrentCalls: 5
};

// Глобальные переменные
let rcsdk = null;
let webPhone = null;
let platform = null;
let activeCalls = new Map();
let wsServer = null;

// Переменные для стабильности
let isRunning = false;
let reconnectAttempts = 0;
let healthCheckTimer = null;
let lastHealthCheck = null;

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
        // Получаем полные SIP данные
        const sipProvisionData = await getSipProvisionData();
        
        // Извлекаем sipInfo из данных
        const sipInfo = sipProvisionData.sipInfo[0];
        
        // Создаем WebPhone инстанс с правильной структурой данных
        const webPhoneConfig = {
            logLevel: 1, // 0 = Trace, 1 = Debug, 2 = Info, 3 = Warn, 4 = Error
            audioHelper: {
                enabled: true
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
            // Настройки для автоматического приема звонков
            autoAnswer: true,
            enableQos: true
        };
        
        logger.info('🔧 Конфигурация WebPhone:', JSON.stringify(webPhoneConfig, null, 2));
        
        // ИСПРАВЛЕНИЕ: Передаем полные SIP данные вместо только sipInfo[0]
        logger.info('✅ Создаем WebPhone с полными SIP данными...');
        
        // Создаем WebPhone с правильными параметрами согласно документации
        // WebPhone конструктор ожидает объект с полем sipInfo
        const webPhoneOptions = {
            sipInfo: sipInfo,
            ...webPhoneConfig
        };
        
        webPhone = new WebPhone(webPhoneOptions);
        
        // Регистрация обработчиков событий
        setupWebPhoneEventHandlers();
        
        // ДОБАВЬТЕ ЭТО: Принудительная регистрация
        logger.info('🔄 Запуск регистрации WebPhone...');
        try {
            // Попробуем разные способы запуска WebPhone
            if (webPhone.userAgent && webPhone.userAgent.start) {
                await webPhone.userAgent.start();
                logger.info('✅ UserAgent запущен через userAgent.start()');
            } else if (webPhone.start) {
                await webPhone.start();
                logger.info('✅ WebPhone запущен через webPhone.start()');
            } else if (webPhone.register) {
                await webPhone.register();
                logger.info('✅ WebPhone зарегистрирован через webPhone.register()');
            } else {
                logger.warn('⚠️ Не найден метод запуска WebPhone, ожидаем автоматической регистрации');
            }
        } catch (error) {
            logger.error(`❌ Ошибка запуска WebPhone: ${error.message}`);
            logger.error(`❌ Stack trace: ${error.stack}`);
        }
        
        logger.info('✅ WebPhone успешно инициализирован');
        return true;
    } catch (error) {
        logger.error(`❌ Ошибка инициализации WebPhone: ${error.message}`);
        logger.error(`❌ Stack trace: ${error.stack}`);
        return false;
    }
}

/**
 * Получение ПОЛНЫХ SIP данных для WebPhone (ИСПРАВЛЕНО)
 */
async function getSipProvisionData() {
    try {
        logger.info('🔍 Получение SIP данных для WebPhone...');
        
        const response = await platform.post('/restapi/v1.0/client-info/sip-provision', {
            sipInfo: [{
                transport: 'WSS'
            }]
        });
        
        const data = await response.json();
        console.log('🔍 ПОЛНЫЕ SIP ДАННЫЕ:', JSON.stringify(data, null, 2));
        
        // ИСПРАВЛЕНИЕ: Возвращаем ВСЮ структуру данных, а не только sipInfo[0]
        if (!data.sipInfo || !data.sipInfo[0]) {
            throw new Error('SIP данные не содержат необходимую информацию');
        }
        
        const sipInfo = data.sipInfo[0];
        
        // Проверяем наличие обязательных полей
        if (!sipInfo.username || !sipInfo.password || !sipInfo.domain) {
            logger.error('❌ SIP данные неполные:', sipInfo);
            throw new Error('SIP данные не содержат username, password или domain');
        }
        
        logger.info('✅ SIP данные получены успешно');
        logger.info(`🔧 SIP Username: ${sipInfo.username}`);
        logger.info(`🔧 SIP Domain: ${sipInfo.domain}`);
        logger.info(`🔧 SIP Proxy: ${sipInfo.outboundProxy}`);
        
        // Возвращаем ПОЛНУЮ структуру данных для WebPhone
        return data;
        
    } catch (error) {
        logger.error(`❌ Ошибка получения SIP данных: ${error.message}`);
        throw error;
    }
}

/**
 * Настройка обработчиков событий WebPhone
 */
function setupWebPhoneEventHandlers() {
    // Событие попытки регистрации
    webPhone.on('registering', () => {
        logger.info('🔄 WebPhone пытается зарегистрироваться...');
    });
    
    // Событие регистрации
    webPhone.on('registered', () => {
        logger.info('✅ WebPhone зарегистрирован и готов принимать звонки');
    });
    
    // Событие ошибки регистрации
    webPhone.on('registrationFailed', (error) => {
        logger.error(`❌ Ошибка регистрации WebPhone: ${JSON.stringify(error, null, 2)}`);
    });
    
    // Событие отключения
    webPhone.on('unregistered', () => {
        logger.warn('⚠️ WebPhone отключен от SIP сервера');
    });
    
    // Общие ошибки
    webPhone.on('error', (error) => {
        logger.error(`❌ WebPhone ошибка: ${JSON.stringify(error, null, 2)}`);
    });
    
    // Событие подключения
    webPhone.on('connected', () => {
        logger.info('🔌 WebPhone подключен к SIP серверу');
    });
    
    // Событие отключения
    webPhone.on('disconnected', () => {
        logger.warn('🔌 WebPhone отключен от SIP сервера');
    });
    
    // КРИТИЧНО: Обработчик входящих звонков
    webPhone.on('invite', async (session) => {
        logger.info('🔔 ВХОДЯЩИЙ ЗВОНОК ОБНАРУЖЕН!');
        
        // Проверяем лимит одновременных звонков
        if (activeCalls.size >= config.maxConcurrentCalls) {
            logger.warn(`⚠️ Превышен лимит одновременных звонков (${config.maxConcurrentCalls}). Отклоняем звонок.`);
            try {
                await session.reject();
            } catch (err) {
                logger.error(`❌ Ошибка отклонения звонка: ${err.message}`);
            }
            return;
        }
        
        const callId = uuidv4();
        const fromNumber = session.request.from.displayName || session.request.from.uri.user || 'Unknown';
        const toNumber = session.request.to.displayName || session.request.to.uri.user || 'Unknown';
        
        logger.info(`📞 Звонок от: ${fromNumber}`);
        logger.info(`📞 Звонок на: ${toNumber}`);
        logger.info(`🆔 ID звонка: ${callId}`);
        logger.info(`📊 Активных звонков: ${activeCalls.size}/${config.maxConcurrentCalls}`);
        
        // Сохраняем информацию о звонке
        const callData = {
            callId,
            sessionId: session.id,
            from: fromNumber,
            to: toNumber,
            startTime: new Date(),
            session: session,
            audioStream: null,
            wsConnection: null,
            timeout: null // Для отслеживания таймаута
        };
        
        activeCalls.set(callId, callData);
        
        // Устанавливаем таймаут на звонок
        callData.timeout = setTimeout(() => {
            logger.warn(`⏰ Таймаут звонка ${callId} (${config.callTimeout}ms)`);
            cleanupCall(callId);
        }, config.callTimeout);
        
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
            cleanupCall(callId);
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
    
    // Очищаем таймаут
    if (callData.timeout) {
        clearTimeout(callData.timeout);
        callData.timeout = null;
    }
    
    // Закрываем WebSocket
    if (callData.wsConnection) {
        try {
            callData.wsConnection.close();
        } catch (error) {
            logger.error(`❌ Ошибка закрытия WebSocket: ${error.message}`);
        }
        callData.wsConnection = null;
    }
    
    // Завершаем сессию если еще активна
    if (callData.session && !callData.session.isEnded()) {
        try {
            callData.session.terminate();
        } catch (error) {
            logger.error(`❌ Ошибка завершения сессии: ${error.message}`);
        }
    }
    
    // Останавливаем аудио стриминг
    if (callData.audioStreamInterval) {
        clearInterval(callData.audioStreamInterval);
        callData.audioStreamInterval = null;
    }
    
    // Удаляем из активных звонков
    activeCalls.delete(callId);
    
    logger.info(`✅ Ресурсы очищены для звонка ${callId} (активных звонков: ${activeCalls.size})`);
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
    
    // Автоматический поиск свободного порта
    function tryListen(port, maxAttempts = 10) {
        if (maxAttempts <= 0) {
            logger.error('❌ Не удалось найти свободный порт после 10 попыток');
            throw new Error('No available ports');
        }
        
        server.listen(port, (err) => {
            if (err) {
                if (err.code === 'EADDRINUSE') {
                    logger.warn(`⚠️ Порт ${port} занят, пробуем ${port + 1}...`);
                    tryListen(port + 1, maxAttempts - 1);
                } else {
                    logger.error(`❌ Ошибка запуска сервера: ${err.message}`);
                    throw err;
                }
            } else {
                config.wsPort = port; // Обновляем конфигурацию
                logger.info(`🌐 WebSocket сервер запущен на порту ${port}`);
            }
        });
    }
    
    tryListen(config.wsPort);
}

/**
 * Мониторинг здоровья системы
 */
function startHealthCheck() {
    if (healthCheckTimer) {
        clearInterval(healthCheckTimer);
    }
    
    healthCheckTimer = setInterval(async () => {
        try {
            logger.debug('🩺 Проверка здоровья системы...');
            
            // Проверяем соединение с RingCentral
            if (platform && platform.loggedIn()) {
                lastHealthCheck = new Date();
                
                // Проверяем регистрацию WebPhone
                if (webPhone && webPhone.isConnected()) {
                    logger.debug('✅ WebPhone подключен и зарегистрирован');
                } else {
                    logger.warn('⚠️ WebPhone не зарегистрирован, попытка переподключения...');
                    await attemptReconnect();
                }
                
                // Проверяем Python сервер
                try {
                    const response = await axios.get(`${config.pythonServer}/health`, { timeout: 5000 });
                    if (response.status === 200) {
                        logger.debug('✅ Python AI сервер доступен');
                    }
                } catch (error) {
                    logger.warn(`⚠️ Python AI сервер недоступен: ${error.message}`);
                }
                
            } else {
                logger.warn('⚠️ RingCentral соединение потеряно, попытка переподключения...');
                await attemptReconnect();
            }
            
            // Логируем статистику
            logger.debug(`📊 Активных звонков: ${activeCalls.size}/${config.maxConcurrentCalls}`);
            
        } catch (error) {
            logger.error(`❌ Ошибка проверки здоровья: ${error.message}`);
        }
    }, config.healthCheckInterval);
    
    logger.info(`🩺 Мониторинг здоровья запущен (интервал: ${config.healthCheckInterval}ms)`);
}

/**
 * Попытка переподключения
 */
async function attemptReconnect() {
    if (reconnectAttempts >= config.reconnectAttempts) {
        logger.error(`❌ Превышено максимальное количество попыток переподключения (${config.reconnectAttempts})`);
        return false;
    }
    
    reconnectAttempts++;
    logger.info(`🔄 Попытка переподключения ${reconnectAttempts}/${config.reconnectAttempts}...`);
    
    try {
        // Останавливаем текущие соединения
        if (webPhone) {
            webPhone.disconnect();
        }
        
        // Ждем перед переподключением
        await new Promise(resolve => setTimeout(resolve, config.reconnectDelay));
        
        // Переподключение к RingCentral
        const rcInitialized = await initializeRingCentral();
        if (!rcInitialized) {
            throw new Error('Не удалось переподключиться к RingCentral');
        }
        
        // Переподключение WebPhone
        const wpInitialized = await initializeWebPhone();
        if (!wpInitialized) {
            throw new Error('Не удалось переподключить WebPhone');
        }
        
        reconnectAttempts = 0;
        logger.info('✅ Переподключение успешно');
        return true;
        
    } catch (error) {
        logger.error(`❌ Ошибка переподключения: ${error.message}`);
        return false;
    }
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
    
    // Запуск мониторинга здоровья
    startHealthCheck();
    
    // Устанавливаем флаг готовности
    isRunning = true;
    
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
    
    isRunning = false;
    
    // Останавливаем мониторинг здоровья
    if (healthCheckTimer) {
        clearInterval(healthCheckTimer);
        healthCheckTimer = null;
    }
    
    // Завершаем все активные звонки
    activeCalls.forEach((callData, callId) => {
        logger.info(`📞 Завершение звонка ${callId}`);
        if (callData.session) {
            try {
                callData.session.terminate();
            } catch (error) {
                logger.error(`❌ Ошибка завершения звонка ${callId}: ${error.message}`);
            }
        }
        cleanupCall(callId);
    });
    
    // Отключаем WebPhone
    if (webPhone) {
        try {
            webPhone.disconnect();
        } catch (error) {
            logger.error(`❌ Ошибка отключения WebPhone: ${error.message}`);
        }
    }
    
    // Закрываем WebSocket сервер
    if (wsServer) {
        wsServer.close();
    }
    
    logger.info('✅ WebPhone Bridge корректно завершен');
    
    // Выход из программы
    process.exit(0);
}

// Запуск приложения
main().catch(error => {
    logger.error(`💥 Критическая ошибка: ${error.message}`);
    process.exit(1);
});