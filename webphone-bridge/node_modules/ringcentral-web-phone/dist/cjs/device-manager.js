"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.DefaultDeviceManager = void 0;
class DefaultDeviceManager {
    async getInputDeviceId() {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const defaultInputDevice = devices.find((device) => device.kind === "audioinput");
        return defaultInputDevice.deviceId;
    }
    async getOutputDeviceId() {
        const devices = await navigator.mediaDevices.enumerateDevices();
        const defaultOutputDevice = devices.find((device) => device.kind === "audiooutput");
        return defaultOutputDevice?.deviceId;
    }
}
exports.DefaultDeviceManager = DefaultDeviceManager;
