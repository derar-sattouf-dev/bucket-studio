import type { ImageGroup, ImageRecord } from "../../../types/image";

/** Callbacks for actions on one or more images (keys are S3 source keys). */
export interface ImageActionHandlers {
    /** Opens the process dialog for these keys. */
    onProcess: (keys: string[]) => void;
    /** Opens the process dialog for every image of the group, loaded or not. */
    onProcessGroup: (group: ImageGroup) => void;
    /** Publishes every publishable image of the group, loaded or not (in the background). */
    onPublishGroup: (group: ImageGroup) => void;
    onPublish: (keys: string[]) => void;
    onRestore: (keys: string[]) => void;
    onReset: (keys: string[]) => void;
    onAbort: (key: string) => void;
    onSaveNotes: (key: string, notes: string | null, tags: string | null) => Promise<void>;
    onView: (image: ImageRecord) => void;
}

export interface ImageBusyState {
    publishing: boolean;
    restoring: boolean;
    resetting: boolean;
    aborting: Set<string>;
}
