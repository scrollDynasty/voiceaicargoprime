import type { DeviceManager } from "./types.js";
export declare class DefaultDeviceManager implements DeviceManager {
    getInputDeviceId(): Promise<string>;
    getOutputDeviceId(): Promise<string | undefined>;
}
