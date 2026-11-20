import { useEffect, useId, useState } from "react";
import { App, Button, Card, Input, Space, Typography } from "antd";
import { ImportOutlined } from "@ant-design/icons";
import { getErrorMessage } from "../../api/client";
import { importFromUrls } from "../../api/imports";
import { fetchSettings } from "../../api/settings";
import { PageContainer } from "../../components/PageContainer";
import { PageHeader } from "../../components/PageHeader";
import type { ImportResult } from "../../types/import";
import { pluralize } from "../../utils/format";
import { ImportResults } from "./components/ImportResults";
import { IMPORT_LIMITS, normaliseFolder, parseUrlList, validateFolder, validateUrls } from "./importValidation";

const { Text } = Typography;

/** Download images from public URLs into a folder of the source prefix. */
export default function ImportPage() {
    const { message } = App.useApp();
    const id = useId();
    const [urlText, setUrlText] = useState("");
    const [folder, setFolder] = useState("");
    const [sourcePrefix, setSourcePrefix] = useState<string | null>(null);
    const [submitting, setSubmitting] = useState(false);
    const [result, setResult] = useState<ImportResult | null>(null);

    useEffect(() => {
        fetchSettings().then(settings => setSourcePrefix(settings.source_prefix)).catch(() => setSourcePrefix(null));
    }, []);

    const urls = parseUrlList(urlText);
    const normalisedFolder = normaliseFolder(folder);
    const urlError = urlText.trim() ? validateUrls(urls) : null;
    const folderError = validateFolder(normalisedFolder);

    async function handleSubmit() {
        const problem = validateUrls(urls) ?? folderError;
        if (problem) {
            message.error(problem);
            return;
        }
        setSubmitting(true);
        try {
            setResult(await importFromUrls({ urls, folder: normalisedFolder }));
        } catch (error) {
            message.error(getErrorMessage(error, "Import failed"));
        } finally {
            setSubmitting(false);
        }
    }

    return (
        <PageContainer>
            <PageHeader
                icon={<ImportOutlined />} iconColor="#13c2c2" tint="#e6fffb"
                title="Import"
                subtitle="Download images from public URLs into the bucket. They are added as pending, no sync needed."
            />

            <Card style={{ borderRadius: 12, marginBottom: 20, maxWidth: 900 }}>
                <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
                    <div>
                        <label htmlFor={`${id}-urls`} style={{ fontWeight: 600, display: "block", marginBottom: 4 }}>
                            Image URLs <Text type="secondary" style={{ fontWeight: 400 }}>(one per line, up to {IMPORT_LIMITS.maxUrls})</Text>
                        </label>
                        <Input.TextArea
                            id={`${id}-urls`} rows={10} value={urlText} onChange={event => setUrlText(event.target.value)}
                            placeholder={"https://example.com/photos/beach.jpg\nhttps://example.com/photos/sunset.png"}
                            status={urlError ? "error" : undefined} aria-describedby={`${id}-urls-help`}
                            style={{ fontFamily: "ui-monospace, SFMono-Regular, Menlo, monospace", fontSize: 12 }}
                        />
                        <Text id={`${id}-urls-help`} type={urlError ? "danger" : "secondary"} style={{ fontSize: 12 }}>
                            {urlError ?? `${urls.length} ${pluralize(urls.length, "URL")} (duplicates and blank lines are ignored)`}
                        </Text>
                    </div>
                    <div>
                        <label htmlFor={`${id}-folder`} style={{ fontWeight: 600, display: "block", marginBottom: 4 }}>Target folder</label>
                        <Space.Compact style={{ width: "100%", maxWidth: 560 }}>
                            <Space.Addon>{sourcePrefix ?? "source prefix /"}</Space.Addon>
                            <Input
                                id={`${id}-folder`} value={folder} onChange={event => setFolder(event.target.value)}
                                onBlur={() => setFolder(normalisedFolder)} placeholder="imports/2024/ (empty = prefix root)"
                                status={folderError ? "error" : undefined} aria-describedby={`${id}-folder-help`}
                            />
                        </Space.Compact>
                        <Text id={`${id}-folder-help`} type={folderError ? "danger" : "secondary"} style={{ display: "block", fontSize: 12 }}>
                            {folderError ?? "Relative to the source prefix. File names come from the URLs; clashes get -2, -3, …"}
                        </Text>
                    </div>
                    <div>
                        <Button type="primary" icon={<ImportOutlined />} loading={submitting} onClick={() => void handleSubmit()}
                                disabled={urls.length === 0 || Boolean(urlError) || Boolean(folderError)}>
                            Import {urls.length > 0 ? `${urls.length} ${pluralize(urls.length, "image")}` : ""}
                        </Button>
                    </div>
                </div>
            </Card>

            {result && <div style={{ maxWidth: 900 }}><ImportResults result={result} /></div>}
        </PageContainer>
    );
}
