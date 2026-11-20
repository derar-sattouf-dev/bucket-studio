import { Button, Tag } from "antd";
import { SyncOutlined } from "@ant-design/icons";

export interface SyncState {
    syncing: boolean;
    autoSyncing: boolean;
    onSync: () => void;
    onCancel: () => void;
}

/** "Syncing" badge, Sync bucket button and Stop button. */
export function SyncButtons({ syncing, autoSyncing, onSync, onCancel, block }: SyncState & { block?: boolean }) {
    return (
        <>
            {autoSyncing && !syncing && <Tag icon={<SyncOutlined spin />} color="processing" style={{ borderRadius: 6 }}>Syncing</Tag>}
            <Button block={block} icon={<SyncOutlined />} loading={syncing} onClick={onSync} style={{ flex: block ? 1 : undefined }}>Sync bucket</Button>
            {(syncing || autoSyncing) && <Button danger onClick={onCancel}>Stop sync</Button>}
        </>
    );
}
