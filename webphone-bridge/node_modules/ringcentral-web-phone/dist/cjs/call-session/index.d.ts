import EventEmitter from "../event-emitter.js";
import type InboundMessage from "../sip-message/inbound.js";
import type WebPhone from "../index.js";
import OutboundCallSession from "./outbound.js";
interface CommandResult {
    code: number;
    description: string;
}
type ParkResult = CommandResult & {
    "park extension": string;
};
type FlipResult = CommandResult & {
    number: string;
    target: string;
};
declare class CallSession extends EventEmitter {
    webPhone: WebPhone;
    sipMessage: InboundMessage;
    localPeer: string;
    remotePeer: string;
    rtcPeerConnection: RTCPeerConnection;
    _mediaStream?: MediaStream;
    audioElement: HTMLAudioElement;
    state: "init" | "ringing" | "answered" | "disposed" | "failed";
    direction: "inbound" | "outbound";
    inputDeviceId: string;
    outputDeviceId: string | undefined;
    private reqid;
    private sdpVersion;
    constructor(webPhone: WebPhone);
    get mediaStream(): MediaStream | undefined;
    set mediaStream(stream: MediaStream);
    private _callId;
    get callId(): string;
    get sessionId(): string;
    get partyId(): string;
    get remoteNumber(): string;
    get localNumber(): string;
    get remoteTag(): string;
    get localTag(): string;
    get isConference(): boolean;
    init(): Promise<void>;
    changeInputDevice(deviceId: string): Promise<void>;
    changeOutputDevice(deviceId: string): Promise<void>;
    transfer(target: string): Promise<void>;
    warmTransfer(target: string): Promise<{
        complete: () => Promise<void>;
        cancel: () => Promise<void>;
        newSession: OutboundCallSession;
    }>;
    completeWarmTransfer(existingSession: CallSession): Promise<void>;
    hangup(): Promise<void>;
    startRecording(): Promise<CommandResult>;
    stopRecording(): Promise<CommandResult>;
    flip(target: string): Promise<FlipResult>;
    park(): Promise<ParkResult>;
    hold(): Promise<void>;
    unhold(): Promise<void>;
    mute(): void;
    unmute(): void;
    sendDtmf(tones: string, duration?: number, interToneGap?: number): void;
    dispose(): void;
    protected toggleTrack(enabled: boolean): void;
    reInvite(toReceive?: boolean): Promise<void>;
    handleReInvite(reInviteMessage: InboundMessage): Promise<void>;
    protected toggleReceive(toReceive: boolean): Promise<void>;
    protected sendJsonMessage<T>(command: "callpark" | "callflip" | "startcallrecord" | "stopcallrecord", args?: {
        [key: string]: string;
    }): Promise<T>;
    protected _transfer(uri: string): Promise<void>;
}
export default CallSession;
