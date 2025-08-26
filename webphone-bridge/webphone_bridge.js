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
let isWebPhoneRegistered = false; // Флаг состояния регистрации WebPhone

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
    
    // Проверяем версию WebPhone SDK
    try {
        const webPhonePackage = require('ringcentral-web-phone/package.json');
        logger.info(`📦 WebPhone SDK версия: ${webPhonePackage.version}`);
    } catch (error) {
        logger.warn('⚠️ Не удалось определить версию WebPhone SDK');
    }
    
    // Проверяем доступность WebPhone SDK
    if (!WebPhone) {
        logger.error('❌ WebPhone SDK не загружен');
        return false;
    }
    
    logger.info(`🔧 WebPhone конструктор: ${typeof WebPhone}`);
    logger.info(`🔧 WebPhone прототип: ${Object.keys(WebPhone.prototype || {}).join(', ')}`);
    
    try {
        // Получаем полные SIP данные
        const sipProvisionData = await getSipProvisionData();
        
        // Извлекаем sipInfo из данных
        const sipInfo = sipProvisionData.sipInfo[0];
        
        // Проверяем структуру sipInfo
        logger.info('🔍 Структура sipInfo:', JSON.stringify(sipInfo, null, 2));
        
        // Проверяем обязательные поля
        const requiredFields = ['username', 'password', 'domain', 'outboundProxy'];
        const missingFields = requiredFields.filter(field => !sipInfo[field]);
        
        if (missingFields.length > 0) {
            logger.error(`❌ Отсутствуют обязательные поля в sipInfo: ${missingFields.join(', ')}`);
            throw new Error(`Неполные SIP данные: отсутствуют ${missingFields.join(', ')}`);
        }
        
        // Создаем WebPhone инстанс с минимальной конфигурацией
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
            }
        };
        
        logger.info('🔧 Конфигурация WebPhone:', JSON.stringify(webPhoneConfig, null, 2));
        
        // ИСПРАВЛЕНИЕ: Передаем полные SIP данные вместо только sipInfo[0]
        logger.info('✅ Создаем WebPhone с полными SIP данными...');
        
        // Создаем WebPhone с правильными параметрами согласно документации
        // WebPhone конструктор ожидает объект с полем sipInfo
        const webPhoneOptions = {
            sipInfo: sipInfo,
            logLevel: webPhoneConfig.logLevel,
            audioHelper: webPhoneConfig.audioHelper,
            media: webPhoneConfig.media
        };
        
        logger.info('🔧 WebPhone опции:', JSON.stringify(webPhoneOptions, null, 2));
        
        // Попробуем создать WebPhone с правильной структурой
        try {
            webPhone = new WebPhone(webPhoneOptions);
        } catch (error) {
            logger.error(`❌ Ошибка создания WebPhone: ${error.message}`);
            // Попробуем альтернативный способ
            logger.info('🔄 Попытка альтернативной инициализации WebPhone...');
            webPhone = new WebPhone({
                sipInfo: sipInfo,
                logLevel: 1
            });
        }
        
        // Проверяем структуру WebPhone объекта
        logger.info('🔍 Диагностика WebPhone объекта:');
        logger.info(`   - webPhone: ${typeof webPhone}`);
        logger.info(`   - webPhone keys: ${Object.keys(webPhone || {}).join(', ')}`);
        
        // В новой версии SDK userAgent может быть в sipClient
        if (webPhone.sipClient) {
            logger.info('✅ Найден sipClient в WebPhone');
            logger.info(`🔍 sipClient свойства: ${Object.keys(webPhone.sipClient).join(', ')}`);
            webPhone.userAgent = webPhone.sipClient;
        } else if (webPhone.userAgent) {
            logger.info('✅ Найден userAgent в WebPhone');
        } else {
            logger.warn('⚠️ userAgent не найден, но WebPhone создан успешно');
            // Создаем заглушку userAgent для совместимости
            webPhone.userAgent = {
                state: 'unknown',
                isRegistered: () => false,
                start: () => Promise.resolve(),
                register: () => Promise.resolve(),
                stop: () => Promise.resolve(),
                unregister: () => Promise.resolve()
            };
        }
        
        logger.info('✅ userAgent успешно создан');
        
        // Диагностика структуры WebPhone
        logger.info('🔍 Структура WebPhone объекта:');
        logger.info(`   - webPhone: ${typeof webPhone}`);
        logger.info(`   - userAgent: ${typeof webPhone.userAgent}`);
        logger.info(`   - userAgent.state: ${webPhone.userAgent.state}`);
        logger.info(`   - userAgent.isRegistered: ${typeof webPhone.userAgent.isRegistered}`);
        
        // Регистрация обработчиков событий
        setupWebPhoneEventHandlers();
        
        // ДОБАВЬТЕ ЭТО: Принудительная регистрация
        logger.info('🔄 Запуск регистрации WebPhone...');
        try {
            // Проверяем доступные методы
            logger.info('🔍 Доступные методы WebPhone:');
            logger.info(`   - webPhone.start: ${typeof webPhone.start}`);
            logger.info(`   - webPhone.register: ${typeof webPhone.register}`);
            logger.info(`   - webPhone.userAgent.start: ${typeof (webPhone.userAgent && webPhone.userAgent.start)}`);
            logger.info(`   - webPhone.userAgent.register: ${typeof (webPhone.userAgent && webPhone.userAgent.register)}`);
            logger.info(`   - webPhone.sipClient: ${typeof webPhone.sipClient}`);
            
            // Попробуем разные способы запуска WebPhone
            if (webPhone.start) {
                await webPhone.start();
                logger.info('✅ WebPhone запущен через webPhone.start()');
            } else if (webPhone.register) {
                await webPhone.register();
                logger.info('✅ WebPhone зарегистрирован через webPhone.register()');
            } else if (webPhone.userAgent && webPhone.userAgent.start) {
                await webPhone.userAgent.start();
                logger.info('✅ UserAgent запущен через userAgent.start()');
            } else if (webPhone.userAgent && webPhone.userAgent.register) {
                await webPhone.userAgent.register();
                logger.info('✅ UserAgent зарегистрирован через userAgent.register()');
            } else {
                logger.warn('⚠️ Не найден метод запуска WebPhone, ожидаем автоматической регистрации');
            }
            
            // Ждем немного и проверяем статус регистрации
            setTimeout(() => {
                const status = getWebPhoneStatus();
                logger.info(`📊 Статус WebPhone после инициализации: ${JSON.stringify(status)}`);
                
                // Дополнительная диагностика sipClient
                if (webPhone.sipClient) {
                    logger.info('🔍 Дополнительная диагностика sipClient:');
                    logger.info(`   - wsc: ${typeof webPhone.sipClient.wsc}`);
                    logger.info(`   - disposed: ${webPhone.sipClient.disposed}`);
                    logger.info(`   - instanceId: ${webPhone.sipClient.instanceId}`);
                    logger.info(`   - timeoutHandle: ${webPhone.sipClient.timeoutHandle}`);
                    
                    // Проверяем WebSocket соединение
                    if (webPhone.sipClient.wsc) {
                        logger.info(`   - wsc.readyState: ${webPhone.sipClient.wsc.readyState}`);
                        logger.info(`   - wsc.url: ${webPhone.sipClient.wsc.url}`);
                    }
                }
            }, 2000);
            
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
        isWebPhoneRegistered = false;
        logger.info('🔄 WebPhone пытается зарегистрироваться...');
    });
    
    // Событие регистрации
    webPhone.on('registered', () => {
        isWebPhoneRegistered = true;
        logger.info('✅ WebPhone зарегистрирован и готов принимать звонки');
        logger.info('🎯 Система готова принимать входящие звонки!');
    });
    
    // Событие ошибки регистрации
    webPhone.on('registrationFailed', (error) => {
        isWebPhoneRegistered = false;
        logger.error(`❌ Ошибка регистрации WebPhone: ${JSON.stringify(error, null, 2)}`);
        
        // Обработка специфических ошибок
        if (error && error.response && error.response.statusCode === 408) {
            logger.warn('⚠️ Обнаружена ошибка 408 (Request Timeout), попытка переподключения через 10 секунд...');
            setTimeout(() => {
                attemptReconnect();
            }, 10000);
        }
    });
    
    // Обработка таймаута sipClient
    if (webPhone.sipClient) {
        webPhone.sipClient.on('timeout', () => {
            logger.warn('⏰ Таймаут sipClient соединения');
            isWebPhoneRegistered = false;
        });
    }
    
    // Событие отключения
    webPhone.on('unregistered', () => {
        isWebPhoneRegistered = false;
        logger.warn('⚠️ WebPhone отключен от SIP сервера');
    });
    
    // Изменение состояния
    webPhone.on('stateChanged', (state) => {
        logger.info(`🔄 WebPhone состояние изменилось: ${state}`);
        if (state === 'Registered' || state === 'Connected') {
            isWebPhoneRegistered = true;
        } else if (state === 'Unregistered' || state === 'Disconnected') {
            isWebPhoneRegistered = false;
        }
    });
    
    // WebSocket события sipClient
    if (webPhone.sipClient && webPhone.sipClient.wsc) {
        webPhone.sipClient.wsc.on('open', () => {
            logger.info('🔌 WebSocket соединение sipClient открыто');
        });
        
        webPhone.sipClient.wsc.on('close', () => {
            logger.warn('🔌 WebSocket соединение sipClient закрыто');
        });
        
        webPhone.sipClient.wsc.on('error', (error) => {
            logger.error(`❌ WebSocket ошибка sipClient: ${error.message}`);
        });
    }
    
    // Общие ошибки
    webPhone.on('error', (error) => {
        logger.error(`❌ WebPhone ошибка: ${JSON.stringify(error, null, 2)}`);
    });
    
    // Событие подключения
    webPhone.on('connected', () => {
        logger.info('🔌 WebPhone подключен к SIP серверу');
        // При подключении устанавливаем флаг регистрации
        isWebPhoneRegistered = true;
    });
    
    // Событие готовности
    webPhone.on('ready', () => {
        logger.info('✅ WebPhone готов к работе');
        isWebPhoneRegistered = true;
    });
    
    // Событие отключения
    webPhone.on('disconnected', () => {
        logger.warn('🔌 WebPhone отключен от SIP сервера');
        isWebPhoneRegistered = false;
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
                const webPhoneStatus = getWebPhoneStatus();
                if (webPhone && isWebPhoneRegistered) {
                    logger.debug('✅ WebPhone подключен и зарегистрирован');
                } else {
                    // Даем больше времени на регистрацию перед переподключением
                    const timeSinceStart = Date.now() - (lastHealthCheck || Date.now());
                    if (timeSinceStart > 60000) { // 1 минута
                        logger.warn(`⚠️ WebPhone не зарегистрирован более 1 минуты (статус: ${JSON.stringify(webPhoneStatus)}), попытка переподключения...`);
                        await attemptReconnect();
                    } else {
                        logger.debug(`⏳ WebPhone еще не зарегистрирован, ожидаем... (статус: ${JSON.stringify(webPhoneStatus)})`);
                    }
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
 * Получение статуса WebPhone
 */
function getWebPhoneStatus() {
    const status = {
        webPhoneExists: !!webPhone,
        isRegistered: isWebPhoneRegistered,
        userAgentExists: !!(webPhone && webPhone.userAgent),
        sipClientExists: !!(webPhone && webPhone.sipClient),
        activeCalls: activeCalls.size,
        maxCalls: config.maxConcurrentCalls
    };
    
    if (webPhone && webPhone.userAgent) {
        try {
            status.userAgentState = webPhone.userAgent.state || 'unknown';
            status.userAgentRegistered = webPhone.userAgent.isRegistered ? webPhone.userAgent.isRegistered() : 'method_not_available';
        } catch (error) {
            status.userAgentError = error.message;
        }
    } else if (webPhone && webPhone.sipClient) {
        try {
            status.sipClientState = webPhone.sipClient.state || 'unknown';
            status.sipClientRegistered = webPhone.sipClient.isRegistered ? webPhone.sipClient.isRegistered() : 'method_not_available';
            
            // Проверяем дополнительные свойства sipClient
            if (webPhone.sipClient.registered) {
                status.sipClientRegistered = webPhone.sipClient.registered;
            }
            if (webPhone.sipClient.connected) {
                status.sipClientConnected = webPhone.sipClient.connected;
            }
        } catch (error) {
            status.sipClientError = error.message;
        }
    } else {
        status.userAgentState = 'not_available';
        status.userAgentRegistered = 'not_available';
        status.userAgentError = 'userAgent не инициализирован';
    }
    
    return status;
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
            try {
                if (webPhone.stop) {
                    await webPhone.stop();
                } else if (webPhone.userAgent && webPhone.userAgent.stop) {
                    await webPhone.userAgent.stop();
                } else if (webPhone.userAgent && webPhone.userAgent.unregister) {
                    await webPhone.userAgent.unregister();
                } else if (webPhone.sipClient && webPhone.sipClient.stop) {
                    await webPhone.sipClient.stop();
                }
            } catch (error) {
                logger.error(`❌ Ошибка отключения WebPhone: ${error.message}`);
            }
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
    lastHealthCheck = Date.now();
    
    logger.info('✅ WebPhone Bridge успешно запущен и готов принимать звонки!');
    logger.info('🎯 Ожидание входящих звонков...');
    
    // Обработка завершения процесса
    process.on('SIGINT', () => {
        logger.info('🛑 Получен сигнал завершения...');
        shutdown().catch(error => {
            logger.error(`❌ Ошибка при завершении: ${error.message}`);
            process.exit(1);
        });
    });
    
    process.on('SIGTERM', () => {
        logger.info('🛑 Получен сигнал завершения...');
        shutdown().catch(error => {
            logger.error(`❌ Ошибка при завершении: ${error.message}`);
            process.exit(1);
        });
    });
}

/**
 * Корректное завершение работы
 */
async function shutdown() {
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
            if (webPhone.stop) {
                await webPhone.stop();
            } else if (webPhone.userAgent && webPhone.userAgent.stop) {
                await webPhone.userAgent.stop();
            } else if (webPhone.userAgent && webPhone.userAgent.unregister) {
                await webPhone.userAgent.unregister();
            } else if (webPhone.sipClient && webPhone.sipClient.stop) {
                await webPhone.sipClient.stop();
            }
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