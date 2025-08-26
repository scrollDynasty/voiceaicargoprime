class EventEmitter {
    // deno-lint-ignore no-explicit-any
    listeners = new Map();
    // This is used to store temporary listeners that are only called once
    // deno-lint-ignore no-explicit-any
    tempListeners = new Map();
    // deno-lint-ignore no-explicit-any
    on(eventName, listener) {
        if (!this.listeners.has(eventName)) {
            this.listeners.set(eventName, []);
        }
        this.listeners.get(eventName).push(listener);
    }
    // deno-lint-ignore no-explicit-any
    once(eventName, listener) {
        if (!this.tempListeners.has(eventName)) {
            this.tempListeners.set(eventName, []);
        }
        this.tempListeners.get(eventName).push(listener);
    }
    // deno-lint-ignore no-explicit-any
    off(eventName, listener) {
        let list = this.listeners.get(eventName);
        if (list) {
            this.listeners.set(eventName, list.filter((l) => l !== listener));
        }
        list = this.tempListeners.get(eventName);
        if (list) {
            this.tempListeners.set(eventName, list.filter((l) => l !== listener));
        }
    }
    // deno-lint-ignore no-explicit-any
    emit(eventName, ...args) {
        (this.listeners.get(eventName) ?? []).forEach((listener) => listener(...args));
        (this.tempListeners.get(eventName) ?? []).forEach((listener) => listener(...args));
        this.tempListeners.delete(eventName);
    }
    removeAllListeners() {
        this.listeners.clear();
        this.tempListeners.clear();
    }
}
export default EventEmitter;
