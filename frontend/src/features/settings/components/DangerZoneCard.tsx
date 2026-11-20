import { Button, Card, Typography } from "antd";
import { DeleteOutlined } from "@ant-design/icons";
import { FieldDesc } from "./FieldDesc";

const { Text } = Typography;

export function DangerZoneCard({ canReset, onResetDb }: { canReset: boolean; onResetDb: () => void }) {
    return (
        <Card
            title={<Text type="danger" strong>Danger zone</Text>}
            size="small"
            style={{ borderRadius: 12, borderTop: "3px solid #ff4d4f", borderColor: "#ffccc7" }}
        >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16 }}>
                <div>
                    <Text strong>Reset database</Text>
                    <FieldDesc>Deletes every image record. Files in the bucket are not touched. Needs the admin password.</FieldDesc>
                </div>
                <Button danger icon={<DeleteOutlined />} onClick={onResetDb} disabled={!canReset}>Reset database</Button>
            </div>
        </Card>
    );
}
