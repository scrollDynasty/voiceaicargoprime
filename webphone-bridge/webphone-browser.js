/**
 * WebPhone Browser Script
 * Runs in the browser context with real WebRTC support
 */

let sdk = null;
let webPhone = null;
let wsConnection = null;
let currentSession = null;

// Logging function that sends logs to Node.js
function log(level, message, data = {}) {
    const logEntry = {
        timestamp: new Date().toISOString(),
        level,
        message,
        data
    };
    
    console.log(`[${level}] ${message}`, data);
    
    // Send log to Node.js via WebSocket
    if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
        wsConnection.send(JSON.stringify({
            type: 'log',
            ...logEntry
        }));
    }
}

// Update status in UI and send to Node.js
function updateStatus(status, details = {}) {
    document.getElementById('status').textContent = status;
    
    if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
        wsConnection.send(JSON.stringify({
            type: 'status',
            status,
            details
        }));
    }
}

// Initialize WebSocket connection to Node.js
function initializeWebSocket() {
    return new Promise((resolve, reject) => {
        wsConnection = new WebSocket('ws://localhost:8082');
        
        wsConnection.onopen = () => {
            log('info', '✅ WebSocket connected to Node.js');
            resolve();
        };
        
        wsConnection.onerror = (error) => {
            log('error', '❌ WebSocket error', { error: error.message });
            reject(error);
        };
        
        wsConnection.onclose = () => {
            log('warn', '⚠️ WebSocket disconnected from Node.js');
            // Attempt to reconnect after 5 seconds
            setTimeout(() => {
                log('info', '🔄 Attempting to reconnect WebSocket...');
                initializeWebSocket().catch(console.error);
            }, 5000);
        };
        
        wsConnection.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                handleNodeMessage(message);
            } catch (error) {
                log('error', '❌ Failed to parse message from Node.js', { error: error.message });
            }
        };
    });
}

// Handle messages from Node.js
function handleNodeMessage(message) {
    switch (message.type) {
        case 'command':
            handleCommand(message.command, message.data);
            break;
        case 'config':
            // Update configuration if needed
            break;
        default:
            log('warn', `Unknown message type: ${message.type}`);
    }
}

// Handle commands from Node.js
function handleCommand(command, data) {
    switch (command) {
        case 'makeCall':
            makeOutgoingCall(data.phoneNumber);
            break;
        case 'endCall':
            if (currentSession) {
                currentSession.dispose();
            }
            break;
        case 'mute':
            if (currentSession) {
                currentSession.mute();
            }
            break;
        case 'unmute':
            if (currentSession) {
                currentSession.unmute();
            }
            break;
        default:
            log('warn', `Unknown command: ${command}`);
    }
}

// Initialize RingCentral SDK and WebPhone
async function initializeWebPhone() {
    try {
        updateStatus('Initializing SDK...');
        
        // Get configuration from window object (injected by Puppeteer)
        const config = window.RINGCENTRAL_CONFIG;
        if (!config) {
            throw new Error('No configuration found. Please inject RINGCENTRAL_CONFIG.');
        }
        
        // Initialize SDK
        sdk = new RingCentral.SDK({
            clientId: config.clientId,
            clientSecret: config.clientSecret,
            server: config.server || 'https://platform.ringcentral.com'
        });
        
        log('info', '🚀 SDK initialized', { clientId: config.clientId });
        updateStatus('Logging in...');
        
        // Login with JWT
        await sdk.login({ jwt: config.jwtToken });
        log('info', '✅ Successfully logged in');
        
        // Get extension info
        const extensionInfo = await sdk.platform().get('/restapi/v1.0/account/~/extension/~');
        const extension = await extensionInfo.json();
        log('info', `📞 Extension: ${extension.extensionNumber} - ${extension.name}`);
        
        updateStatus('Registering WebPhone...');
        
        // Create WebPhone instance
        webPhone = new RingCentral.WebPhone(sdk, {
            appName: 'VoiceAI Bridge',
            appVersion: '2.0.0',
            audioHelper: {
                enabled: true,
                incoming: 'audio/incoming.mp3',
                outgoing: 'audio/outgoing.mp3'
            },
            logLevel: 3, // Detailed logging
            enableDscp: true,
            enableQos: true,
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
        });
        
        // Register WebPhone
        await webPhone.register();
        log('info', '✅ WebPhone registered successfully');
        updateStatus('Ready - Waiting for calls...');
        
        // Set up event handlers
        setupWebPhoneEventHandlers();
        
    } catch (error) {
        log('error', '❌ Failed to initialize WebPhone', { 
            error: error.message,
            stack: error.stack 
        });
        updateStatus(`Error: ${error.message}`);
        throw error;
    }
}

// Set up WebPhone event handlers
function setupWebPhoneEventHandlers() {
    // Handle incoming calls
    webPhone.on('call', (session) => {
        log('info', '📞 Incoming call detected!', {
            sessionId: session.id,
            from: session.request.from.displayName || session.request.from.uri.user,
            to: session.request.to.displayName || session.request.to.uri.user
        });
        
        currentSession = session;
        
        // Update UI
        document.getElementById('call-info').innerHTML = `
            <h2>Incoming Call</h2>
            <p>From: ${session.request.from.displayName || session.request.from.uri.user}</p>
            <p>Status: Ringing</p>
        `;
        
        // Notify Node.js about incoming call
        if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
            wsConnection.send(JSON.stringify({
                type: 'incomingCall',
                sessionId: session.id,
                from: session.request.from.uri.user,
                fromName: session.request.from.displayName,
                to: session.request.to.uri.user,
                toName: session.request.to.displayName
            }));
        }
        
        // Auto-answer the call
        setTimeout(() => {
            log('info', '🤖 Auto-answering call...');
            session.accept()
                .then(() => {
                    log('info', '✅ Call answered successfully');
                    setupCallSession(session);
                })
                .catch((error) => {
                    log('error', '❌ Failed to answer call', { error: error.message });
                });
        }, 1000);
    });
    
    // Handle registration events
    webPhone.on('registered', () => {
        log('info', '✅ WebPhone registered with SIP server');
        updateStatus('Registered - Ready for calls');
    });
    
    webPhone.on('unregistered', () => {
        log('warn', '⚠️ WebPhone unregistered from SIP server');
        updateStatus('Unregistered');
    });
    
    webPhone.on('registrationFailed', (error) => {
        log('error', '❌ WebPhone registration failed', { error });
        updateStatus('Registration failed');
    });
}

// Set up call session handlers and audio streaming
function setupCallSession(session) {
    let audioContext = null;
    let mediaStreamSource = null;
    let scriptProcessor = null;
    
    // Update UI
    document.getElementById('call-info').innerHTML = `
        <h2>Active Call</h2>
        <p>With: ${session.request.from.displayName || session.request.from.uri.user}</p>
        <p>Status: Connected</p>
        <p>Duration: <span id="duration">00:00</span></p>
    `;
    
    // Start duration timer
    let startTime = Date.now();
    const durationInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        const minutes = Math.floor(elapsed / 60).toString().padStart(2, '0');
        const seconds = (elapsed % 60).toString().padStart(2, '0');
        document.getElementById('duration').textContent = `${minutes}:${seconds}`;
    }, 1000);
    
    // Handle session events
    session.on('accepted', () => {
        log('info', '✅ Call accepted');
        
        // Get remote media stream
        const remoteStream = session.getRemoteStreams()[0];
        if (remoteStream) {
            log('info', '🎵 Remote audio stream available', {
                tracks: remoteStream.getTracks().map(t => ({ 
                    kind: t.kind, 
                    id: t.id, 
                    enabled: t.enabled 
                }))
            });
            
            // Set up audio processing
            setupAudioProcessing(remoteStream);
        }
    });
    
    session.on('muted', () => {
        log('info', '🔇 Call muted');
    });
    
    session.on('unmuted', () => {
        log('info', '🔊 Call unmuted');
    });
    
    session.on('hold', () => {
        log('info', '⏸️ Call on hold');
    });
    
    session.on('unhold', () => {
        log('info', '▶️ Call resumed');
    });
    
    session.on('bye', () => {
        log('info', '👋 Call ended');
        clearInterval(durationInterval);
        document.getElementById('call-info').innerHTML = '';
        currentSession = null;
        
        // Clean up audio processing
        if (scriptProcessor) {
            scriptProcessor.disconnect();
        }
        if (mediaStreamSource) {
            mediaStreamSource.disconnect();
        }
        if (audioContext) {
            audioContext.close();
        }
        
        // Notify Node.js
        if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
            wsConnection.send(JSON.stringify({
                type: 'callEnded',
                sessionId: session.id
            }));
        }
    });
    
    session.on('failed', (response, cause) => {
        log('error', '❌ Call failed', { response, cause });
        clearInterval(durationInterval);
        document.getElementById('call-info').innerHTML = `<p style="color: red;">Call failed: ${cause}</p>`;
        currentSession = null;
    });
    
    // Set up audio processing for the remote stream
    function setupAudioProcessing(stream) {
        try {
            audioContext = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 16000 // Match Python AI expectations
            });
            
            mediaStreamSource = audioContext.createMediaStreamSource(stream);
            
            // Create script processor for audio chunks
            scriptProcessor = audioContext.createScriptProcessor(4096, 1, 1);
            
            scriptProcessor.onaudioprocess = (event) => {
                const inputData = event.inputBuffer.getChannelData(0);
                
                // Convert Float32Array to Int16Array
                const int16Data = new Int16Array(inputData.length);
                for (let i = 0; i < inputData.length; i++) {
                    const s = Math.max(-1, Math.min(1, inputData[i]));
                    int16Data[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                }
                
                // Send audio data to Node.js
                if (wsConnection && wsConnection.readyState === WebSocket.OPEN) {
                    wsConnection.send(new Blob([int16Data.buffer], { type: 'audio/raw' }));
                }
            };
            
            // Connect the nodes
            mediaStreamSource.connect(scriptProcessor);
            scriptProcessor.connect(audioContext.destination);
            
            log('info', '🎵 Audio processing started', {
                sampleRate: audioContext.sampleRate,
                state: audioContext.state
            });
            
        } catch (error) {
            log('error', '❌ Failed to set up audio processing', { error: error.message });
        }
    }
}

// Make outgoing call
async function makeOutgoingCall(phoneNumber) {
    try {
        log('info', `📞 Making outgoing call to ${phoneNumber}`);
        const session = await webPhone.call(phoneNumber);
        currentSession = session;
        setupCallSession(session);
    } catch (error) {
        log('error', '❌ Failed to make outgoing call', { error: error.message });
    }
}

// Initialize everything when page loads
window.addEventListener('DOMContentLoaded', async () => {
    try {
        // First connect WebSocket
        await initializeWebSocket();
        
        // Then initialize WebPhone
        await initializeWebPhone();
        
    } catch (error) {
        console.error('Failed to initialize:', error);
        updateStatus(`Failed to initialize: ${error.message}`);
    }
});

// Handle page unload
window.addEventListener('beforeunload', () => {
    if (webPhone) {
        webPhone.unregister();
    }
    if (wsConnection) {
        wsConnection.close();
    }
});