// Audio Stream Fix for WebPhone Bridge
// This file contains the critical audio stream simulation code to prevent voicemail redirect

// Add this class after MockRTCPeerConnection definition

class AudioStreamSimulator {
    constructor() {
        this.isActive = false;
        this.statsInterval = null;
        this.keepAliveInterval = null;
    }

    start(peerConnection) {
        if (this.isActive) return;
        
        console.log('🔊 Starting audio stream simulation...');
        this.isActive = true;
        
        // Simulate active RTP stream statistics
        this.statsInterval = setInterval(() => {
            if (!this.isActive) {
                clearInterval(this.statsInterval);
                return;
            }
            console.log('🎵 Audio stream active, simulating RTP packets...');
        }, 1000);
        
        // Keep tracks active
        this.keepAliveInterval = setInterval(() => {
            if (!this.isActive) {
                clearInterval(this.keepAliveInterval);
                return;
            }
            
            // Mark all audio tracks as active
            if (global.activeMediaTracks) {
                global.activeMediaTracks.forEach(track => {
                    if (track.kind === 'audio' && track._enabled) {
                        console.log('🎤 Keeping audio track active:', track.id);
                        // Prevent track from being garbage collected
                        track._lastActivity = Date.now();
                    }
                });
            }
        }, 2000);
    }

    stop() {
        console.log('🔇 Stopping audio stream simulation...');
        this.isActive = false;
        
        if (this.statsInterval) {
            clearInterval(this.statsInterval);
            this.statsInterval = null;
        }
        
        if (this.keepAliveInterval) {
            clearInterval(this.keepAliveInterval);
            this.keepAliveInterval = null;
        }
    }
}

// Enhanced MockRTCPeerConnection methods to add:

const enhancedMethods = {
    getSenders: function() {
        console.log('🔧 MockRTCPeerConnection: getSenders вызван');
        return this._senders || [];
    },
    
    getReceivers: function() {
        console.log('🔧 MockRTCPeerConnection: getReceivers вызван');
        return this._receivers || [];
    },
    
    getStats: function() {
        console.log('🔧 MockRTCPeerConnection: getStats вызван');
        const stats = new Map();
        
        // Simulate active audio transmission
        if (this._audioStreamActive) {
            const now = Date.now();
            
            stats.set('outbound-rtp-audio', {
                type: 'outbound-rtp',
                kind: 'audio',
                mediaType: 'audio',
                ssrc: 12345,
                timestamp: now,
                bytesSent: Math.floor(now / 100) * 160, // ~16KB/s for audio
                packetsSent: Math.floor(now / 20), // ~50 packets/sec
                packetsLost: 0,
                jitter: 0.001,
                roundTripTime: 0.050,
                // Additional fields RingCentral might check
                headerBytesSent: Math.floor(now / 100) * 20,
                retransmittedPacketsSent: 0,
                retransmittedBytesSent: 0,
                targetBitrate: 32000,
                totalEncodedBytesTarget: Math.floor(now / 100) * 160,
                framesEncoded: Math.floor(now / 40), // 25 fps
                totalEncodeTime: now / 1000,
                totalPacketSendDelay: 0.1,
                qualityLimitationReason: 'none',
                qualityLimitationResolutionChanges: 0,
                contentType: 'audio',
                encoderImplementation: 'opus'
            });
            
            stats.set('candidate-pair', {
                type: 'candidate-pair',
                state: 'succeeded',
                priority: 1,
                nominated: true,
                bytesSent: Math.floor(now / 100) * 200,
                bytesReceived: Math.floor(now / 100) * 200,
                timestamp: now,
                transportId: 'transport-1',
                localCandidateId: 'local-1',
                remoteCandidateId: 'remote-1',
                totalRoundTripTime: 0.100,
                currentRoundTripTime: 0.050,
                availableOutgoingBitrate: 128000,
                availableIncomingBitrate: 128000,
                requestsReceived: Math.floor(now / 1000),
                requestsSent: Math.floor(now / 1000),
                responsesReceived: Math.floor(now / 1000),
                responsesSent: Math.floor(now / 1000),
                consentRequestsSent: Math.floor(now / 5000),
                packetsReceived: Math.floor(now / 20),
                packetsSent: Math.floor(now / 20)
            });
            
            stats.set('media-source', {
                type: 'media-source',
                kind: 'audio',
                trackIdentifier: 'audio-track-1',
                timestamp: now,
                audioLevel: 0.5,
                totalAudioEnergy: now / 10000,
                totalSamplesDuration: now / 1000,
                echoReturnLoss: 50,
                echoReturnLossEnhancement: 30
            });
        }
        
        return Promise.resolve(stats);
    },
    
    _startAudioStreamSimulation: function() {
        if (this._audioStreamActive) return;
        
        console.log('🔊 Starting audio stream simulation in PeerConnection...');
        this._audioStreamActive = true;
        
        // Create audio simulator instance
        if (!this._audioSimulator) {
            this._audioSimulator = new AudioStreamSimulator();
        }
        this._audioSimulator.start(this);
    },
    
    _stopAudioStreamSimulation: function() {
        console.log('🔇 Stopping audio stream simulation in PeerConnection...');
        this._audioStreamActive = false;
        
        if (this._audioSimulator) {
            this._audioSimulator.stop();
            this._audioSimulator = null;
        }
    }
};

// Modified inboundCall handler with audio keep-alive
const enhancedInboundCallHandler = `
// 🔊 КРИТИЧНО: Поддерживаем активное аудио соединение
if (inboundCallSession.peerConnection) {
    console.log('🎵 Запускаем поддержку активного аудио соединения...');
    
    // Ensure PeerConnection has audio simulation methods
    const pc = inboundCallSession.peerConnection;
    if (!pc._startAudioStreamSimulation && pc.constructor.name === 'MockRTCPeerConnection') {
        Object.assign(pc, enhancedMethods);
        pc._senders = pc._senders || [];
        pc._receivers = pc._receivers || [];
        pc._audioStreamActive = false;
    }
    
    // Start audio simulation
    if (pc._startAudioStreamSimulation) {
        pc._startAudioStreamSimulation();
    }
    
    // Keep-alive interval
    const keepAliveInterval = setInterval(async () => {
        try {
            const state = inboundCallSession.state;
            if (state === 'Established' || state === 'Answered' || state === 'Proceeding') {
                // Get stats to show activity
                if (pc.getStats) {
                    const stats = await pc.getStats();
                    console.log('📊 Audio connection active, stats updated:', stats.size, 'entries');
                }
                
                // Send keepalive if method exists
                if (inboundCallSession.keepAlive) {
                    await inboundCallSession.keepAlive();
                }
            } else if (state === 'Terminated' || state === 'Disposed') {
                clearInterval(keepAliveInterval);
            }
        } catch (err) {
            console.error('⚠️ Keep-alive error:', err.message);
        }
    }, 3000); // Every 3 seconds
    
    // Clean up on call end
    inboundCallSession.once('disposed', () => {
        clearInterval(keepAliveInterval);
        if (pc._stopAudioStreamSimulation) {
            pc._stopAudioStreamSimulation();
        }
        console.log('🔇 Audio support stopped for ended call');
    });
}
`;

module.exports = {
    AudioStreamSimulator,
    enhancedMethods,
    enhancedInboundCallHandler
};