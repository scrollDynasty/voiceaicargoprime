declare class EventEmitter {
    private listeners;
    private tempListeners;
    on(eventName: string, listener: (...args: any[]) => void): void;
    once(eventName: string, listener: (...args: any[]) => void): void;
    off(eventName: string, listener: (...args: any[]) => void): void;
    emit(eventName: string, ...args: any[]): void;
    removeAllListeners(): void;
}
export default EventEmitter;
