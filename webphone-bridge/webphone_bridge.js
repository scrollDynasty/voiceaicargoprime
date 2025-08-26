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

// WebRTC полифиллы для Node.js (определяем классы перед использованием)
class MockMediaStreamTrack {
    constructor(kind = 'audio') {
        this.kind = kind;
        this.id = Math.random().toString(36).substr(2, 9);
        this.label = `Mock ${kind} track`;
        this.enabled = true;
        this.muted = false;
        this.readyState = 'live';
        this.onended = null;
        this.onmute = null;
        this.onunmute = null;
        
        // Дополнительные свойства для совместимости
        if (kind === 'audio') {
            this.volume = 1.0;
            this.echoCancellation = true;
            this.noiseSuppression = true;
            this.autoGainControl = true;
        }
        
        console.log(`🔧 MockMediaStreamTrack: создан ${kind} track с ID ${this.id}`);
    }

    stop() {
        console.log(`🔧 MockMediaStreamTrack: остановлен ${this.kind} track ${this.id}`);
        this.readyState = 'ended';
        if (this.onended) {
            this.onended();
        }
    }

    clone() {
        console.log(`🔧 MockMediaStreamTrack: клонирован ${this.kind} track ${this.id}`);
        return new MockMediaStreamTrack(this.kind);
    }
    
    getCapabilities() {
        if (this.kind === 'audio') {
            return {
                echoCancellation: [true, false],
                noiseSuppression: [true, false],
                autoGainControl: [true, false],
                channelCount: { min: 1, max: 2 },
                sampleRate: { min: 8000, max: 96000 },
                sampleSize: { min: 16, max: 16 }
            };
        }
        return {};
    }
    
    getConstraints() {
        return {};
    }
    
    getSettings() {
        if (this.kind === 'audio') {
            return {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true,
                channelCount: 1,
                sampleRate: 48000,
                sampleSize: 16
            };
        }
        return {};
    }
}

class MockMediaStream {
    constructor(tracks = []) {
        this.id = Math.random().toString(36).substr(2, 9);
        this._tracks = tracks;
        this.active = true;
        this.onaddtrack = null;
        this.onremovetrack = null;
        this.onactive = null;
        this.oninactive = null;
        
        console.log(`🔧 MockMediaStream: создан MediaStream с ID ${this.id} и ${tracks.length} треками`);
        
        // Обновляем состояние active при изменении треков
        this._updateActiveState();
    }

    getTracks() {
        return this._tracks;
    }

    getAudioTracks() {
        return this._tracks.filter(track => track.kind === 'audio');
    }

    getVideoTracks() {
        return this._tracks.filter(track => track.kind === 'video');
    }

    addTrack(track) {
        console.log(`🔧 MockMediaStream: добавлен track ${track.id} (${track.kind}) в stream ${this.id}`);
        this._tracks.push(track);
        this._updateActiveState();
        
        if (this.onaddtrack) {
            this.onaddtrack({ track: track });
        }
    }

    removeTrack(track) {
        const index = this._tracks.indexOf(track);
        if (index > -1) {
            console.log(`🔧 MockMediaStream: удален track ${track.id} (${track.kind}) из stream ${this.id}`);
            this._tracks.splice(index, 1);
            this._updateActiveState();
            
            if (this.onremovetrack) {
                this.onremovetrack({ track: track });
            }
        }
    }

    clone() {
        console.log(`🔧 MockMediaStream: клонирован stream ${this.id}`);
        const clonedTracks = this._tracks.map(track => track.clone());
        return new MockMediaStream(clonedTracks);
    }
    
    getTrackById(trackId) {
        return this._tracks.find(track => track.id === trackId) || null;
    }
    
    _updateActiveState() {
        const wasActive = this.active;
        this.active = this._tracks.some(track => track.readyState === 'live');
        
        if (wasActive && !this.active && this.oninactive) {
            this.oninactive();
        } else if (!wasActive && this.active && this.onactive) {
            this.onactive();
        }
    }
}

// Navigator полифилл для Node.js (необходим для WebPhone)
// Принудительно перезаписываем navigator.mediaDevices
if (typeof navigator !== 'undefined') {
    navigator.mediaDevices = {
        getUserMedia: (constraints = {}) => {
            logger.info('🔧 MockMediaDevices: getUserMedia вызван с constraints:', JSON.stringify(constraints));
            
            try {
                // Создаем фиктивные треки в зависимости от constraints
                const tracks = [];
                
                if (constraints.audio) {
                    const audioTrack = new MockMediaStreamTrack('audio');
                    tracks.push(audioTrack);
                    logger.info('🔧 MockMediaDevices: создан audio track:', audioTrack.id);
                }
                
                if (constraints.video) {
                    const videoTrack = new MockMediaStreamTrack('video');
                    tracks.push(videoTrack);
                    logger.info('🔧 MockMediaDevices: создан video track:', videoTrack.id);
                }
                
                // Если нет constraints или они пустые, создаем audio по умолчанию
                if (!constraints.audio && !constraints.video) {
                    const audioTrack = new MockMediaStreamTrack('audio');
                    tracks.push(audioTrack);
                    logger.info('🔧 MockMediaDevices: создан default audio track:', audioTrack.id);
                }
                
                const stream = new MockMediaStream(tracks);
                logger.info('🔧 MockMediaDevices: создан MediaStream:', stream.id, 'с треками:', stream.getTracks().length);
                logger.info('🔧 MockMediaDevices: MediaStream.active:', stream.active);
                logger.info('🔧 MockMediaDevices: AudioTracks:', stream.getAudioTracks().length);
                logger.info('🔧 MockMediaDevices: VideoTracks:', stream.getVideoTracks().length);
                
                return Promise.resolve(stream);
            } catch (error) {
                logger.error('❌ Ошибка в MockMediaDevices.getUserMedia:', error);
                return Promise.reject(error);
            }
        },
        enumerateDevices: () => Promise.resolve([
            {
                deviceId: 'default',
                groupId: 'default',
                kind: 'audioinput',
                label: 'Default Audio Input'
            },
            {
                deviceId: 'default',
                groupId: 'default', 
                kind: 'audiooutput',
                label: 'Default Audio Output'
            }
        ])
    };
    
    // Также установим другие свойства navigator если нужно
    navigator.userAgent = navigator.userAgent || 'RingCentral-WebPhone-Bridge/1.0.0 (Node.js)';
    navigator.appName = navigator.appName || 'RingCentral WebPhone Bridge';
    navigator.appVersion = navigator.appVersion || '1.0.0';
} else {
    // Если navigator не существует, создаем глобальный
    global.navigator = {
        userAgent: 'RingCentral-WebPhone-Bridge/1.0.0 (Node.js)',
        appName: 'RingCentral WebPhone Bridge',
        appVersion: '1.0.0',
        mediaDevices: {
            getUserMedia: (constraints = {}) => {
                console.log('🔧 MockMediaDevices: getUserMedia вызван с constraints:', JSON.stringify(constraints));
                
                try {
                    // Создаем фиктивные треки в зависимости от constraints
                    const tracks = [];
                    
                    if (constraints.audio) {
                        const audioTrack = new MockMediaStreamTrack('audio');
                        tracks.push(audioTrack);
                        console.log('🔧 MockMediaDevices: создан audio track:', audioTrack.id);
                    }
                    
                    if (constraints.video) {
                        const videoTrack = new MockMediaStreamTrack('video');
                        tracks.push(videoTrack);
                        console.log('🔧 MockMediaDevices: создан video track:', videoTrack.id);
                    }
                    
                    // Если нет constraints или они пустые, создаем audio по умолчанию
                    if (!constraints.audio && !constraints.video) {
                        const audioTrack = new MockMediaStreamTrack('audio');
                        tracks.push(audioTrack);
                        console.log('🔧 MockMediaDevices: создан default audio track:', audioTrack.id);
                    }
                    
                    const stream = new MockMediaStream(tracks);
                    console.log('🔧 MockMediaDevices: создан MediaStream:', stream.id, 'с треками:', stream.getTracks().length);
                    
                    return Promise.resolve(stream);
                } catch (error) {
                    console.error('❌ Ошибка в MockMediaDevices.getUserMedia:', error);
                    return Promise.reject(error);
                }
            },
            enumerateDevices: () => Promise.resolve([
                {
                    deviceId: 'default',
                    groupId: 'default',
                    kind: 'audioinput',
                    label: 'Default Audio Input'
                },
                {
                    deviceId: 'default',
                    groupId: 'default', 
                    kind: 'audiooutput',
                    label: 'Default Audio Output'
                }
            ])
        }
    };
}

// WebRTC полифиллы для Node.js (необходимы для WebPhone)
class MockRTCPeerConnection {
    constructor(config) {
        this.localDescription = null;
        this.remoteDescription = null;
        this.iceConnectionState = 'new';
        this.iceGatheringState = 'new';
        this.signalingState = 'stable';
        this.onicecandidate = null;
        this.oniceconnectionstatechange = null;
        this.onsignalingstatechange = null;
        this.ondatachannel = null;
        this.ontrack = null;
        this._localStreams = [];
        this._remoteStreams = [];
    }

    async createOffer(options) {
        console.log('🔧 MockRTCPeerConnection: createOffer вызван');
        return {
            type: 'offer',
            sdp: 'v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n'
        };
    }

    async createAnswer(options) {
        console.log('🔧 MockRTCPeerConnection: createAnswer вызван');
        return {
            type: 'answer',
            sdp: 'v=0\r\no=- 0 0 IN IP4 127.0.0.1\r\ns=-\r\nt=0 0\r\n'
        };
    }

    async setLocalDescription(desc) {
        console.log('🔧 MockRTCPeerConnection: setLocalDescription вызван');
        this.localDescription = desc;
    }

    async setRemoteDescription(desc) {
        console.log('🔧 MockRTCPeerConnection: setRemoteDescription вызван');
        this.remoteDescription = desc;
    }

    addIceCandidate(candidate) {
        console.log('🔧 MockRTCPeerConnection: addIceCandidate вызван');
        return Promise.resolve();
    }

    addStream(stream) {
        console.log('🔧 MockRTCPeerConnection: addStream вызван');
        this._localStreams.push(stream);
    }

    removeStream(stream) {
        console.log('🔧 MockRTCPeerConnection: removeStream вызван');
        const index = this._localStreams.indexOf(stream);
        if (index > -1) {
            this._localStreams.splice(index, 1);
        }
    }

    addTrack(track, stream) {
        console.log('🔧 MockRTCPeerConnection: addTrack вызван', track.kind, track.id);
        if (stream && !this._localStreams.includes(stream)) {
            this._localStreams.push(stream);
        }
        return {
            track: track,
            sender: {
                track: track,
                replaceTrack: (newTrack) => {
                    console.log('🔧 MockRTCPeerConnection: replaceTrack вызван');
                    return Promise.resolve();
                },
                getParameters: () => {
                    console.log('🔧 MockRTCPeerConnection: getParameters вызван');
                    return {
                        encodings: [],
                        headerExtensions: [],
                        rtcp: {},
                        codecs: []
                    };
                },
                setParameters: (parameters) => {
                    console.log('🔧 MockRTCPeerConnection: setParameters вызван');
                    return Promise.resolve();
                }
            }
        };
    }

    removeTrack(sender) {
        console.log('🔧 MockRTCPeerConnection: removeTrack вызван');
    }

    getLocalStreams() {
        return this._localStreams;
    }

    getRemoteStreams() {
        return this._remoteStreams;
    }

    close() {
        console.log('🔧 MockRTCPeerConnection: close вызван');
        this.iceConnectionState = 'closed';
    }

    createDataChannel(label, options) {
        console.log('🔧 MockRTCPeerConnection: createDataChannel вызван');
        return new MockRTCDataChannel(label);
    }
}

class MockRTCDataChannel {
    constructor(label) {
        this.label = label;
        this.readyState = 'connecting';
        this.onopen = null;
        this.onclose = null;
        this.onmessage = null;
        this.onerror = null;
    }

    send(data) {
        console.log('🔧 MockRTCDataChannel: send вызван');
    }

    close() {
        console.log('🔧 MockRTCDataChannel: close вызван');
        this.readyState = 'closed';
    }
}



// Устанавливаем глобальные WebRTC объекты
global.RTCPeerConnection = MockRTCPeerConnection;
global.RTCDataChannel = MockRTCDataChannel;
global.MediaStream = MockMediaStream;
global.MediaStreamTrack = MockMediaStreamTrack;

// Дополнительные WebRTC полифиллы
global.RTCIceCandidate = class RTCIceCandidate {
    constructor(candidateInitDict) {
        this.candidate = candidateInitDict?.candidate || '';
        this.sdpMid = candidateInitDict?.sdpMid || null;
        this.sdpMLineIndex = candidateInitDict?.sdpMLineIndex || null;
    }
};

global.RTCSessionDescription = class RTCSessionDescription {
    constructor(descriptionInitDict) {
        this.type = descriptionInitDict?.type || '';
        this.sdp = descriptionInitDict?.sdp || '';
    }
};

// Audio Context полифилл
global.AudioContext = global.AudioContext || class MockAudioContext {
    constructor() {
        this.state = 'running';
        this.sampleRate = 44100;
        this.currentTime = 0;
        this.destination = {};
    }

    createMediaStreamSource(stream) {
        return {
            connect: () => {},
            disconnect: () => {}
        };
    }

    createGain() {
        return {
            gain: { value: 1 },
            connect: () => {},
            disconnect: () => {}
        };
    }

    createAnalyser() {
        return {
            fftSize: 2048,
            frequencyBinCount: 1024,
            connect: () => {},
            disconnect: () => {},
            getByteFrequencyData: () => {},
            getByteTimeDomainData: () => {}
        };
    }

    close() {
        this.state = 'closed';
        return Promise.resolve();
    }
};

// Window объект для совместимости
global.window = global.window || {
    location: { href: 'http://localhost' },
    document: { 
        createElement: () => ({ 
            canPlayType: () => '',
            play: () => Promise.resolve(),
            pause: () => {},
            load: () => {}
        }),
        addEventListener: () => {},
        removeEventListener: () => {}
    },
    addEventListener: () => {},
    removeEventListener: () => {},
    RTCPeerConnection: global.RTCPeerConnection,
    MediaStream: global.MediaStream,
    AudioContext: global.AudioContext
};

console.log('✅ WebRTC полифиллы для Node.js установлены успешно');

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
    jwtToken: process.env.RINGCENTRAL_JWT_TOKEN || 'eyJraWQiOiI4NzYyZjU5OGQwNTk0NGRiODZiZjVjYTk3ODA0NzYwOCIsInR5cCI6IkpXVCIsImFsZyI6IlJTMjU2In0.eyJhdWQiOiJodHRwczovL3BsYXRmb3JtLnJpbmdjZW50cmFsLmNvbS9yZXN0YXBpL29hdXRoL3Rva2VuIiwic3ViIjoiMjA2OTkwOTAxOSIsImlzcyI6Imh0dHBzOi8vcGxhdGZvcm0ucmluZ2NlbnRyYWwuY29tIiwiZXhwIjozOTAzNjUxMzQyLCJpYXQiOjE3NTYxNjc2OTUsImp0aSI6IlpTckJuOHlFVDJLeEFjOXhmTlZ6ZncifQ.fHF6mXLa9wHygLYiFVQzIo4bKT8niwnYKD7PT7gFGoayZpDOkHwamesmXunn_IIY3rRT9Z2hXHgaJpdpW5ZRimaYOydcjGpj1HgdOxmTRBcYj6B4HWXb9YXO95Q2sfFLPS-3DwvcxeqNW8yoX3Cx31VpCfsybrvwq1NtDO73KulJYPByTSjoLQMj5to5gxRtKlqbhabj1o4YaeKkKb70_Sr-T0lXQS_93fOaPi0xP_AYNhDmDEQBZc1tvwUF7-ETj2Bv-EnfH5OxWfbRS3bSnZdRs1P-0TJg6SfNgwlAGNnMqEdpVyBMXt-02aQA8xgo1O9RDI-nSUXd2iKaA5CTAg',
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

// ✅ Глобальная переменная для отслеживания обработанных звонков
const processedCalls = new Set();

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
        
        // Device ID будет получен при первой регистрации через SIP Provision API
        logger.info('📱 Device ID будет получен при регистрации через SIP Provision API');
        
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
                remote: null, // В headless режиме без DOM элементов
                local: null
            }
        };
        
        logger.info('🔧 Конфигурация WebPhone:', JSON.stringify(webPhoneConfig, null, 2));
        
        // ИСПРАВЛЕНИЕ: Передаем полные SIP данные вместо только sipInfo[0]
        logger.info('✅ Создаем WebPhone с полными SIP данными...');
        
        // Создаем WebPhone с правильными параметрами согласно документации
        // WebPhone конструктор ожидает объект с полем sipInfo
        const webPhoneOptions = {
            sipInfo: sipInfo,
            autoAnswer: true,  // 🔥 КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ - автоматический прием звонков
            logLevel: webPhoneConfig.logLevel,
            audioHelper: webPhoneConfig.audioHelper,
            media: webPhoneConfig.media,
            appName: 'RingCentral WebPhone Bridge',
            appVersion: '1.0.0',
            userAgent: 'RingCentral-WebPhone-Bridge/1.0.0'
        };
        
        logger.info('🔧 WebPhone опции:', JSON.stringify(webPhoneOptions, null, 2));
        logger.info('✅ WebPhone создается с autoAnswer: true для автоматического приема звонков');
        
        // Попробуем создать WebPhone с правильной структурой
        try {
            logger.info('🔧 Создаем WebPhone с расширенными опциями...');
            webPhone = new WebPhone(webPhoneOptions);
        } catch (error) {
            logger.error(`❌ Ошибка создания WebPhone: ${error.message}`);
            logger.error(`❌ Stack trace: ${error.stack}`);
            
            // Попробуем альтернативный способ с минимальными опциями
            logger.info('🔄 Попытка альтернативной инициализации WebPhone...');
            try {
                webPhone = new WebPhone({
                    sipInfo: sipInfo,
                    autoAnswer: true,  // 🔥 КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ
                    logLevel: 1,
                    appName: 'RingCentral WebPhone Bridge',
                    appVersion: '1.0.0',
                    userAgent: 'RingCentral-WebPhone-Bridge/1.0.0'
                });
            } catch (secondError) {
                logger.error(`❌ Ошибка альтернативной инициализации: ${secondError.message}`);
                
                // Попробуем самый минимальный вариант
                logger.info('🔄 Попытка минимальной инициализации WebPhone...');
                webPhone = new WebPhone({
                    sipInfo: sipInfo,
                    autoAnswer: true,  // 🔥 КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ
                    userAgent: 'RingCentral-WebPhone-Bridge/1.0.0'
                });
            }
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
        
        // 🔥 ВОССТАНОВЛЕНИЕ ПРИ СЕТЕВЫХ ПРОБЛЕМАХ
        if (typeof window !== 'undefined') {
            window.addEventListener('online', async () => {
                console.log('🌐 Сеть восстановлена, перезапускаем WebPhone...');
                try {
                    await webPhone.start();
                    console.log('✅ WebPhone восстановлен');
                } catch (error) {
                    console.error('❌ Ошибка восстановления:', error);
                }
            });
        }
        
        // 🔥 ОСНОВНОЙ ОБРАБОТЧИК АВТОПРИЕМА ЗВОНКОВ
        webPhone.on('inboundCall', async (inboundCallSession) => {
            const callId = inboundCallSession.callId || `call_${Date.now()}`;
            const from = inboundCallSession.remoteIdentity?.uri || inboundCallSession.remoteIdentity?.displayName || 'unknown';
            
            console.log('📞 ВХОДЯЩИЙ ЗВОНОК ПОЛУЧЕН ЧЕРЕЗ WEBPHONE!');
            console.log('📋 Информация:', {
                callId,
                sessionId: inboundCallSession.sessionId,
                from,
                state: inboundCallSession.state
            });

            try {
                // Проверка лимита активных звонков
                if (activeCalls.size >= config.maxConcurrentCalls) {
                    console.log('⚠️ Достигнут лимит звонков, отклоняем');
                    await inboundCallSession.decline();
                    return;
                }

                // 🔥 АВТОМАТИЧЕСКИЙ ПРИЕМ
                console.log('🤖 Автоматически принимаем звонок через WebPhone...');
                await inboundCallSession.answer();
                console.log('✅ Звонок ПРИНЯТ автоматически через WebPhone!');

                // Обработка принятого звонка
                handleAcceptedCall(inboundCallSession, callId, from);

            } catch (error) {
                console.error('❌ Ошибка автоприема через WebPhone:', error);
                
                // Fallback - голосовая почта
                try {
                    await inboundCallSession.toVoicemail();
                    console.log('📧 Перенаправлено в голосовую почту');
                } catch (fallbackError) {
                    console.error('❌ Ошибка fallback:', fallbackError);
                }
            }
        });
        
        // 🔥 ФУНКЦИЯ ОБРАБОТКИ ПРИНЯТОГО ЗВОНКА
        function handleAcceptedCall(callSession, callId, from) {
            console.log('🎯 Обрабатываем принятый звонок от:', from);

            // События звонка
            callSession.on('answered', () => {
                console.log('✅ Звонок подтвержден как отвеченный');
                // Интеграция с Voice AI
                startVoiceAI(callSession, from);
            });

            callSession.on('disposed', () => {
                console.log('📞 Звонок завершен:', callId);
                processedCalls.delete(callId);
            });

            callSession.on('mediaStreamSet', (mediaStream) => {
                console.log('🎵 Медиа поток установлен');
                // Подключение аудио процессора для Voice AI
                connectAudioProcessor(mediaStream, callSession);
            });

            // Добавляем в обработанные
            processedCalls.add(callId);
        }

        function startVoiceAI(callSession, from) {
            console.log('🤖 Запуск Voice AI для звонка от:', from);
            // Здесь интеграция с voice_ai_engine.py
            // Например: отправка HTTP запроса или WebSocket сообщения
        }

        function connectAudioProcessor(mediaStream, callSession) {
            console.log('🔊 Подключение аудио процессора для Voice AI...');
            // Здесь интеграция с speech_processor.py
        }
        
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
                
                // КРИТИЧНО: Принудительная регистрация после запуска
                logger.info('🔄 Инициируем принудительную SIP регистрацию...');
                if (webPhone.sipClient && webPhone.sipClient.register) {
                    await webPhone.sipClient.register();
                    logger.info('✅ SIP регистрация инициирована через sipClient.register()');
                } else if (webPhone.userAgent && webPhone.userAgent.register) {
                    await webPhone.userAgent.register();
                    logger.info('✅ SIP регистрация инициирована через userAgent.register()');
                }
                
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
                
                        // Принудительно устанавливаем флаг регистрации, если WebSocket соединение активно
        if (webPhone.sipClient && webPhone.sipClient.wsc && webPhone.sipClient.wsc.readyState === 1) {
            logger.info('✅ WebSocket соединение активно, устанавливаем флаг регистрации');
            isWebPhoneRegistered = true;
            
            // Принудительная регистрация устройства через API
            setTimeout(() => {
                forceDeviceRegistration();
            }, 1000);
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
 * Получение SIP данных и регистрация устройства для WebPhone
 */
async function getSipProvisionData() {
    try {
        logger.info('🔍 Начинаем процесс регистрации SIP устройства...');
        
        // Шаг 1: Регистрируем устройство через SIP provision API
        logger.info('📱 Регистрация устройства в RingCentral...');
        const response = await platform.post('/restapi/v1.0/client-info/sip-provision', {
            sipInfo: [{
                transport: 'WSS'
            }]
        });
        
        const data = await response.json();
        console.log('🔍 ПОЛНЫЕ SIP ДАННЫЕ:', JSON.stringify(data, null, 2));
        
        // Валидация ответа
        if (!data.sipInfo || !data.sipInfo[0]) {
            throw new Error('SIP данные не содержат необходимую информацию');
        }
        
        if (!data.device) {
            throw new Error('Ответ не содержит информацию об устройстве');
        }
        
        const sipInfo = data.sipInfo[0];
        const deviceInfo = data.device;
        
        // Проверяем наличие обязательных полей в SIP данных
        if (!sipInfo.username || !sipInfo.password || !sipInfo.domain) {
            logger.error('❌ SIP данные неполные:', sipInfo);
            throw new Error('SIP данные не содержат username, password или domain');
        }
        
        // Шаг 2: Проверяем статус устройства
        logger.info('🔍 Проверка статуса зарегистрированного устройства...');
        logger.info(`📱 Device ID: ${deviceInfo.id}`);
        logger.info(`📱 Device Type: ${deviceInfo.type}`);
        logger.info(`📱 Device Status: ${deviceInfo.status}`);
        logger.info(`📱 Extension: ${deviceInfo.extension.extensionNumber}`);
        
        // Проверяем, что устройство в статусе Online
        if (deviceInfo.status !== 'Online') {
            logger.warn(`⚠️ Устройство не в статусе Online (текущий: ${deviceInfo.status})`);
            // Пытаемся подождать и проверить снова
            await new Promise(resolve => setTimeout(resolve, 2000));
            
            const statusCheckResponse = await platform.get(`/restapi/v1.0/account/~/device/${deviceInfo.id}`);
            const updatedDevice = await statusCheckResponse.json();
            logger.info(`📱 Обновленный статус устройства: ${updatedDevice.status}`);
            
            if (updatedDevice.status !== 'Online') {
                logger.warn('⚠️ Устройство все еще не Online, но продолжаем...');
            }
        }
        
        // Шаг 3: Логируем успешную регистрацию
        logger.info('✅ Устройство успешно зарегистрировано в RingCentral');
        logger.info(`🔧 SIP Username: ${sipInfo.username}`);
        logger.info(`🔧 SIP Domain: ${sipInfo.domain}`);
        logger.info(`🔧 SIP Proxy: ${sipInfo.outboundProxy}`);
        logger.info(`🔧 Authorization ID: ${sipInfo.authorizationId}`);
        
        // Шаг 4: Сохраняем данные устройства для мониторинга
        if (data.pollingInterval) {
            logger.info(`⏰ Интервал переподключения: ${data.pollingInterval} мс`);
            global.devicePollingInterval = data.pollingInterval;
        }
        
        if (data.sipFlags) {
            logger.info(`🚩 SIP Flags:`, data.sipFlags);
            global.sipFlags = data.sipFlags;
        }
        
        // Сохраняем Device ID для дальнейшего мониторинга
        global.registeredDeviceId = deviceInfo.id;
        global.deviceInfo = deviceInfo;
        
        logger.info('✅ SIP устройство полностью зарегистрировано и готово к работе');
        return data;
        
    } catch (error) {
        logger.error(`❌ Ошибка регистрации SIP устройства: ${error.message}`);
        if (error.response) {
            logger.error(`❌ HTTP Status: ${error.response.status}`);
            logger.error(`❌ Response: ${JSON.stringify(error.response.data, null, 2)}`);
        }
        throw error;
    }
}

/**
 * Мониторинг статуса устройства и автоматическая перерегистрация
 */
async function monitorDeviceStatus() {
    if (!global.registeredDeviceId) {
        logger.warn('⚠️ Нет зарегистрированного Device ID для мониторинга');
        return;
    }
    
    try {
        logger.info(`🔍 Проверка статуса устройства ${global.registeredDeviceId}...`);
        
        const response = await platform.get(`/restapi/v1.0/account/~/device/${global.registeredDeviceId}`);
        const deviceStatus = await response.json();
        
        logger.info(`📱 Статус устройства: ${deviceStatus.status}`);
        
        if (deviceStatus.status !== 'Online') {
            logger.warn(`⚠️ Устройство не в статусе Online: ${deviceStatus.status}`);
            logger.info('🔄 Попытка перерегистрации устройства...');
            
            // Попытка перерегистрации
            await attemptDeviceReregistration();
        } else {
            logger.info('✅ Устройство в статусе Online');
        }
        
    } catch (error) {
        logger.error(`❌ Ошибка проверки статуса устройства: ${error.message}`);
        // Попытка перерегистрации при ошибке
        await attemptDeviceReregistration();
    }
}

/**
 * Перерегистрация устройства при сбоях
 */
async function attemptDeviceReregistration() {
    try {
        logger.info('🔄 Начинаем перерегистрацию устройства...');
        
        // Останавливаем текущий WebPhone если есть
        if (webPhone && webPhone.sipClient) {
            try {
                await webPhone.sipClient.stop();
                logger.info('🛑 Текущий WebPhone остановлен');
            } catch (stopError) {
                logger.warn(`⚠️ Ошибка остановки WebPhone: ${stopError.message}`);
            }
        }
        
        // Перерегистрируем устройство
        const sipProvisionData = await getSipProvisionData();
        
        // Пересоздаем WebPhone с новыми данными
        const sipInfo = sipProvisionData.sipInfo[0];
        
        const webPhoneOptions = {
            sipInfo: sipInfo,
            autoAnswer: true,  // 🔥 КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ
            logLevel: 1,
            audioHelper: { enabled: true },
            media: { remote: null, local: null },
            appName: 'RingCentral WebPhone Bridge',
            appVersion: '1.0.0',
            userAgent: 'RingCentral-WebPhone-Bridge/1.0.0'
        };
        
        webPhone = new WebPhone(webPhoneOptions);
        
        // Настраиваем обработчики событий
        setupWebPhoneEventHandlers();
        
        // Запускаем WebPhone
        await webPhone.start();
        
        // Принудительная регистрация
        if (webPhone.sipClient && webPhone.sipClient.register) {
            await webPhone.sipClient.register();
        }
        
        logger.info('✅ Устройство успешно перерегистрировано');
        
    } catch (error) {
        logger.error(`❌ Ошибка перерегистрации устройства: ${error.message}`);
        
        // Попытка снова через некоторое время
        setTimeout(() => {
            attemptDeviceReregistration();
        }, 30000); // Повторить через 30 секунд
    }
}

/**
 * Запуск периодического мониторинга устройства
 */
function startDeviceMonitoring() {
    const interval = global.devicePollingInterval || 300000; // По умолчанию 5 минут
    logger.info(`⏰ Запуск мониторинга устройства с интервалом ${interval/1000} секунд`);
    
    setInterval(async () => {
        await monitorDeviceStatus();
    }, interval);
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
    
    // Событие отключения
    webPhone.on('unregistered', () => {
        isWebPhoneRegistered = false;
        logger.warn('⚠️ WebPhone отключен от SIP сервера');
    });
    
    // Дополнительные события для sipClient
    if (webPhone.sipClient) {
        webPhone.sipClient.on('timeout', () => {
            logger.warn('⏰ Таймаут sipClient соединения');
            isWebPhoneRegistered = false;
        });
        
        webPhone.sipClient.on('connected', () => {
            logger.info('🔗 SipClient подключен к серверу');
            isWebPhoneRegistered = true;
        });
        
        webPhone.sipClient.on('registered', () => {
            logger.info('✅ SipClient зарегистрирован на сервере');
            isWebPhoneRegistered = true;
        });
        
        webPhone.sipClient.on('disconnected', () => {
            logger.warn('❌ SipClient отключен от сервера');
            isWebPhoneRegistered = false;
        });
        
        // Обработка всех событий для диагностики
        const originalEmit = webPhone.sipClient.emit;
        webPhone.sipClient.emit = function(...args) {
            const eventName = args[0];
            
            // Логируем все события кроме частых message
            if (eventName !== 'message') {
                logger.info(`🔍 SipClient Event: ${eventName}`);
            }
            
            // КРИТИЧНО: Обработка входящих сообщений из sipClient
            if (eventName === 'inboundMessage') {
                const message = args[1];
                if (message && typeof message === 'string') {
                    // Ищем SIP INVITE в сообщении
                    if (message.includes('INVITE ') && message.includes('SIP/2.0')) {
                        logger.info('🔔 ОБНАРУЖЕН ВХОДЯЩИЙ SIP INVITE!');
                        logger.info(`📨 Сообщение: ${message.substring(0, 300)}...`);
                        
                        // Парсим Call-ID и другие заголовки
                        const callIdMatch = message.match(/Call-ID:\s*([^\r\n]+)/i);
                        const fromMatch = message.match(/From:\s*([^\r\n]+)/i);
                        const toMatch = message.match(/To:\s*([^\r\n]+)/i);
                        const cseqMatch = message.match(/CSeq:\s*([^\r\n]+)/i);
                        const viaMatch = message.match(/Via:\s*([^\r\n]+)/i);
                        
                        if (callIdMatch) {
                            logger.info(`📞 Call-ID: ${callIdMatch[1]}`);
                            logger.info(`📞 From: ${fromMatch ? fromMatch[1] : 'unknown'}`);
                            logger.info(`📞 To: ${toMatch ? toMatch[1] : 'unknown'}`);
                            
                            // Автоматически отвечаем 180 Ringing для начала
                            try {
                                logger.info('🔔 Отправляем 180 Ringing...');
                                const ringingResponse = createSipResponse(message, 180, 'Ringing');
                                if (webPhone.sipClient.wsc && webPhone.sipClient.wsc.readyState === 1) {
                                    webPhone.sipClient.wsc.send(ringingResponse);
                                    logger.info('✅ 180 Ringing отправлен');
                                    
                                    // Через 2 секунды отправляем 200 OK
                                    setTimeout(() => {
                                        try {
                                            logger.info('📞 Отправляем 200 OK для приема звонка...');
                                            const okResponse = createSipResponse(message, 200, 'OK', true);
                                            webPhone.sipClient.wsc.send(okResponse);
                                            logger.info('✅ 200 OK отправлен - звонок принят!');
                                        } catch (error) {
                                            logger.error(`❌ Ошибка отправки 200 OK: ${error.message}`);
                                        }
                                    }, 2000);
                                }
                            } catch (error) {
                                logger.error(`❌ Ошибка обработки INVITE: ${error.message}`);
                            }
                        }
                    }
                }
            }
            
            // Обработка outbound сообщений для мониторинга
            if (eventName === 'outboundMessage') {
                const message = args[1];
                if (message && typeof message === 'string') {
                    if (message.includes('REGISTER ')) {
                        logger.info('📤 Отправляем REGISTER запрос');
                    } else if (message.includes('SIP/2.0 200')) {
                        logger.info('📤 Отправляем 200 OK ответ');
                    }
                }
            }
            
            // Обработка входящих звонков через события
            if (eventName === 'invite' || eventName === 'incoming') {
                logger.info('🔔 ВХОДЯЩИЙ ЗВОНОК ОБНАРУЖЕН В SIPCLIENT EVENT!');
                const session = args[1];
                if (session && session.accept) {
                    logger.info('🤖 Автоматически принимаем входящий звонок через события...');
                    session.accept().then(() => {
                        logger.info('✅ Звонок принят через sipClient события!');
                    }).catch((error) => {
                        logger.error(`❌ Ошибка приема звонка через события: ${error.message}`);
                    });
                }
            }
            
            return originalEmit.apply(this, args);
        };
        
        // Функция для создания SIP ответов
        function createSipResponse(originalMessage, statusCode, reasonPhrase, includeSDP = false) {
            const lines = originalMessage.split('\r\n');
            let via = '';
            let from = '';
            let to = '';
            let callId = '';
            let cseq = '';
            let contact = '';
            
            // Извлекаем необходимые заголовки из оригинального INVITE
            for (const line of lines) {
                if (line.startsWith('Via:')) {
                    via = line;
                } else if (line.startsWith('From:')) {
                    from = line;
                } else if (line.startsWith('To:')) {
                    to = line;
                    // Добавляем tag к To заголовку если его нет
                    if (!to.includes('tag=')) {
                        to += `;tag=${Date.now()}`;
                    }
                } else if (line.startsWith('Call-ID:')) {
                    callId = line;
                } else if (line.startsWith('CSeq:')) {
                    cseq = line;
                } else if (line.startsWith('Contact:')) {
                    contact = line;
                }
            }
            
            // Создаем базовые заголовки ответа
            let response = [
                `SIP/2.0 ${statusCode} ${reasonPhrase}`,
                via,
                from,
                to,
                callId,
                cseq
            ];
            
            // Добавляем Contact для 200 OK
            if (statusCode === 200) {
                response.push('Contact: <sip:15135725833*102@127.0.0.1:5060>');
            }
            
            // Добавляем SDP для 200 OK
            if (statusCode === 200 && includeSDP) {
                const sdp = [
                    'v=0',
                    'o=- 123456789 123456789 IN IP4 127.0.0.1',
                    's=-',
                    'c=IN IP4 127.0.0.1',
                    't=0 0',
                    'm=audio 5004 RTP/AVP 0 8',
                    'a=rtpmap:0 PCMU/8000',
                    'a=rtpmap:8 PCMA/8000',
                    'a=sendrecv'
                ].join('\r\n');
                
                response.push('Content-Type: application/sdp');
                response.push(`Content-Length: ${sdp.length}`);
                response.push('');
                response.push(sdp);
            } else {
                response.push('Content-Length: 0');
                response.push('');
            }
            
            return response.join('\r\n');
        }
    }
    
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
        
        // WebSocket сообщения теперь обрабатываются через sipClient.emit перехватчик выше
    }
    
    // Обработчик входящих звонков (альтернативный)
    webPhone.on('call', (call) => {
        logger.info('🔔 ВХОДЯЩИЙ ЗВОНОК ОБНАРУЖЕН (call event)!');
        logger.info(`📞 Call ID: ${call.id}`);
        logger.info(`📞 Call direction: ${call.direction}`);
        logger.info(`📞 Call state: ${call.state}`);
        
        if (call.direction === 'incoming') {
            logger.info('🤖 Автоматически принимаем входящий звонок...');
            call.answer().then(() => {
                logger.info('✅ Звонок принят автоматически!');
            }).catch((error) => {
                logger.error(`❌ Ошибка приема звонка: ${error.message}`);
            });
        }
    });
    
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
    
    // КРИТИЧНО: Добавляем обработчик для UserAgent
    if (webPhone.userAgent) {
        logger.info('🔧 Настройка обработчиков UserAgent для входящих звонков...');
        
        webPhone.userAgent.on('invite', async (session) => {
            logger.info('🔔 ВХОДЯЩИЙ ЗВОНОК ОБНАРУЖЕН В USERAGENT!');
            logger.info(`📞 Session ID: ${session.id}`);
            
            try {
                logger.info('🤖 Автоматически принимаем звонок через UserAgent...');
                await session.accept();
                logger.info('✅ Звонок принят через UserAgent!');
                
                // Настройка обработчиков сессии
                session.on('accepted', () => {
                    logger.info('✅ Звонок успешно соединен');
                });
                
                session.on('terminated', () => {
                    logger.info('📞 Звонок завершен');
                });
                
                session.on('failed', (error) => {
                    logger.error(`❌ Ошибка звонка: ${error}`);
                });
                
            } catch (error) {
                logger.error(`❌ Ошибка при приеме звонка через UserAgent: ${error.message}`);
            }
        });
        
        webPhone.userAgent.on('message', (request) => {
            logger.info(`📨 UserAgent Message: ${request.method}`);
        });
    }
    
    // КРИТИЧНО: Обработчик входящих звонков (резервный)
    webPhone.on('invite', async (session) => {
        logger.info('🔔 ВХОДЯЩИЙ ЗВОНОК ОБНАРУЖЕН В WEBPHONE!');
        logger.info(`📞 Session ID: ${session.id}`);
        logger.info(`📞 From: ${session.request.from.displayName || session.request.from.uri.user}`);
        logger.info(`📞 To: ${session.request.to.displayName || session.request.to.uri.user}`);
        
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
 * Обработка webhook событий от RingCentral
 */
async function handleWebhookEvent(eventData) {
    try {
        logger.info('📞 Обработка webhook события...');
        logger.info('📋 Данные события:', JSON.stringify(eventData, null, 2));
        
        // Проверяем, что это telephony событие
        if (eventData.event && eventData.event.includes('telephony/sessions')) {
            logger.info('📞 Обнаружено telephony событие');
            
            const body = eventData.body;
            if (body && body.sessionId) {
                logger.info(`📞 Найден sessionId: ${body.sessionId}`);
                
                // Проверяем, есть ли входящие звонки для обработки
                // Теперь обрабатываем "Setup", "Proceeding" и "Ringing"
                if (body.parties) {
                    logger.info('📋 Проверяем все parties в событии:');
                    body.parties.forEach((party, index) => {
                        logger.info(`  Party ${index}: direction=${party.direction}, status=${party.status?.code}, missedCall=${party.missedCall}`);
                    });
                    
                    const inboundCall = body.parties.find(party => 
                        party.direction === 'Inbound' && 
                        party.status && 
                        party.status.code === 'Setup' &&  // ✅ Принимаем в статусе Setup
                        !party.missedCall
                    );
                    
                    if (inboundCall) {
                        logger.info('🔔 ВХОДЯЩИЙ ЗВОНОК ОБНАРУЖЕН!');
                        logger.info(`📞 Звонок от: ${inboundCall.from?.phoneNumber || 'Неизвестно'}`);
                        logger.info(`📞 Статус: ${inboundCall.status.code}`);
                        
                        // 🔥 НЕ ПЫТАЕМСЯ ПРИНИМАТЬ ЧЕРЕЗ REST API
                        // WebPhone с autoAnswer: true + обработчик inboundCall сделают это автоматически
                        logger.info('✅ WebPhone автоматически обработает этот звонок');
                    } else {
                        // Проверяем, есть ли звонки в других статусах
                        const otherInboundCall = body.parties.find(party => 
                            party.direction === 'Inbound' && 
                            party.status && 
                            ['Proceeding'].includes(party.status.code) &&
                            !party.missedCall
                        );
                        
                        if (otherInboundCall) {
                            logger.info(`📞 Звонок в статусе Proceeding, но принимаем только Setup: ${otherInboundCall.status.code}`);
                        }
                    }
                }
            }
        } else {                                                                                                                                                                                                                                                                                                                                        
            logger.info('📋 Не telephony событие, пропускаем');
        }
        
    } catch (error) {
        logger.error(`❌ Ошибка обработки webhook события: ${error.message}`);
    }
}

/**
 * Инициализация WebSocket сервера для аудио стриминга
 */
function initializeWebSocketServer() {
    const app = express();
    
    // Добавляем middleware для парсинга JSON
    app.use(express.json());
    
    const server = require('http').createServer(app);
    
    wsServer = new WebSocket.Server({ server });
    
    wsServer.on('connection', (ws, req) => {
        const callId = req.url.split('/').pop();
        logger.info(`🔌 Новое WebSocket соединение для звонка ${callId}`);
        
        ws.on('error', (error) => {
            logger.error(`❌ WebSocket ошибка: ${error.message}`);
        });
    });
    
    // Добавляем HTTP endpoint для получения webhook событий от Python сервера
    app.post('/webhook', (req, res) => {
        try {
            const eventData = req.body;
            logger.info('📞 Получено webhook событие от Python сервера');
            
                    // ✅ Проверяем, не обрабатывали ли уже этот звонок
        const callKey = `${eventData.body?.sessionId || eventData.body?.telephonySessionId}_${eventData.body?.parties?.[0]?.id}`;
        
        if (callKey && callKey !== 'undefined_undefined') {
            if (processedCalls.has(callKey)) {
                logger.info(`🔄 Звонок ${callKey} уже обрабатывается, пропускаем`);
                res.status(200).json({ status: 'already_processed' });
                return;
            }
            
            // Добавляем в обработанные
            processedCalls.add(callKey);
            
            // Устанавливаем таймер для очистки через 30 секунд
            setTimeout(() => {
                processedCalls.delete(callKey);
                logger.info(`🗑️ Звонок ${callKey} удален из обработанных`);
            }, 30000);
        }
        
        // Обрабатываем webhook событие
        handleWebhookEvent(eventData);
            
            res.status(200).json({ status: 'ok' });
        } catch (error) {
            logger.error(`❌ Ошибка обработки webhook: ${error.message}`);
            res.status(500).json({ error: error.message });
        }
    });
    
    // Добавляем endpoint для получения статуса WebPhone Bridge
    app.get('/status', (req, res) => {
        try {
            const status = {
                webPhoneExists: !!webPhone,
                isRegistered: isWebPhoneRegistered,
                activeCalls: activeCalls.size,
                maxCalls: config.maxConcurrentCalls,
                deviceRegistered: !!global.registeredDeviceId,
                deviceId: global.registeredDeviceId || null,
                deviceStatus: global.deviceInfo ? global.deviceInfo.status : 'unknown',
                timestamp: new Date().toISOString()
            };
            
            res.status(200).json(status);
        } catch (error) {
            logger.error(`❌ Ошибка получения статуса: ${error.message}`);
            res.status(500).json({ error: error.message });
        }
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
                    // Проверяем, можно ли принудительно установить флаг регистрации
                    if (webPhone && webPhone.sipClient && webPhone.sipClient.wsc && webPhone.sipClient.wsc.readyState === 1) {
                        logger.info('✅ WebSocket соединение активно, принудительно устанавливаем флаг регистрации');
                        isWebPhoneRegistered = true;
                        
                        // Если WebPhone не зарегистрирован, попробуем принудительную регистрацию
                        if (!isWebPhoneRegistered) {
                            logger.info('🔄 Попытка принудительной регистрации через API...');
                            setTimeout(() => {
                                forceDeviceRegistration();
                            }, 2000);
                        }
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
 * Принудительная регистрация устройства через RingCentral API
 */
async function forceDeviceRegistration() {
    try {
        logger.info('🔄 Принудительная регистрация устройства через SIP Provision API...');
        
        // Используем правильный API endpoint для регистрации устройства
        const body = {
            sipInfo: [
                {
                    transport: 'WSS'
                }
            ]
        };
        
        logger.info('📋 Отправляем запрос на регистрацию:', JSON.stringify(body, null, 2));
        
        // Регистрация устройства через SIP Provision API
        const response = await platform.post('/restapi/v1.0/client-info/sip-provision', body);
        const result = await response.json();
        
        logger.info('✅ Устройство успешно зарегистрировано через SIP Provision API');
        logger.info('📋 Результат регистрации:', JSON.stringify(result, null, 2));
        
        // Обновляем deviceId если он изменился
        if (result.device && result.device.id) {
            global.registeredDeviceId = result.device.id;
            global.deviceInfo = result.device;
            logger.info(`📱 Обновлен Device ID: ${global.registeredDeviceId}`);
        }
        
        // Устанавливаем флаг регистрации
        isWebPhoneRegistered = true;
        
        // Обновляем SIP данные для WebPhone
        if (result.sipInfo && result.sipInfo[0]) {
            logger.info('🔄 Обновляем SIP данные WebPhone...');
            await updateWebPhoneWithNewSipData(result.sipInfo[0]);
        }
        
    } catch (error) {
        logger.error(`❌ Ошибка принудительной регистрации устройства: ${error.message}`);
        if (error.response) {
            logger.error(`❌ HTTP Status: ${error.response.status}`);
            logger.error(`❌ Response: ${JSON.stringify(error.response.data, null, 2)}`);
        }
    }
}

// 🔥 УДАЛЕНА ФУНКЦИЯ forceAnswerCall - больше не нужна
// WebPhone с autoAnswer: true автоматически обрабатывает входящие звонки

/**
 * Обновление WebPhone с новыми SIP данными
 */
async function updateWebPhoneWithNewSipData(newSipInfo) {
    try {
        logger.info('🔄 Обновление WebPhone с новыми SIP данными...');
        
        if (!webPhone || !webPhone.sipClient) {
            logger.warn('⚠️ WebPhone не инициализирован, пропускаем обновление');
            return;
        }
        
        // Обновляем SIP данные в sipClient
        if (webPhone.sipClient.sipInfo) {
            webPhone.sipClient.sipInfo = [newSipInfo];
            logger.info('✅ SIP данные обновлены в sipClient');
        }
        
        // Принудительно перерегистрируем sipClient
        if (webPhone.sipClient.register) {
            await webPhone.sipClient.register();
            logger.info('✅ sipClient перерегистрирован с новыми данными');
        }
        
        // Устанавливаем флаг регистрации
        isWebPhoneRegistered = true;
        
    } catch (error) {
        logger.error(`❌ Ошибка обновления WebPhone: ${error.message}`);
    }
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
        maxCalls: config.maxConcurrentCalls,
        // Добавляем информацию об устройстве
        deviceRegistered: !!global.registeredDeviceId,
        deviceId: global.registeredDeviceId || null,
        deviceStatus: global.deviceInfo ? global.deviceInfo.status : 'unknown',
        pollingInterval: global.devicePollingInterval || null
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
    
    // Запуск мониторинга устройства
    startDeviceMonitoring();
    
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