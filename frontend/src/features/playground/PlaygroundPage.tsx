import { useState } from "react";
import { Alert, Button, Card, Col, Empty, Row, Space, Spin, Typography } from "antd";
import { DownloadOutlined, ExperimentOutlined, PlayCircleOutlined } from "@ant-design/icons";
import { useLocation, useSearchParams } from "react-router-dom";
import { PageContainer } from "../../components/PageContainer";
import { PageHeader } from "../../components/PageHeader";
import { useObjectUrl } from "../../hooks/useObjectUrl";
import { usePresets } from "../../hooks/usePresets";
import type { PresetConfig, ProcessingEngine } from "../../types/preset";
import type { PlaygroundRecipe } from "../../types/playground";
import { downloadBlob } from "../../utils/download";
import { validatePresetConfig, withDefaults } from "../../utils/presetConfig";
import { CompareView } from "./components/CompareView";
import { RecipePanel } from "./components/RecipePanel";
import { ResultStats } from "./components/ResultStats";
import { SourcePicker, type SourceMode } from "./components/SourcePicker";
import { useImageDimensions } from "./hooks/useImageDimensions";
import { usePlaygroundRun } from "./hooks/usePlaygroundRun";
import { readPlaygroundState } from "./playgroundNavigation";
import type { PlaygroundSource } from "./types";

const { Text } = Typography;

function isHttpUrl(value: string): boolean {
    return /^https?:\/\/\S+$/i.test(value.trim());
}

/** Try a preset (or an unsaved tweak of one) on a single image, then compare and download. */
export default function PlaygroundPage() {
    const location = useLocation();
    const [searchParams] = useSearchParams();
    const presets = usePresets();
    const runner = usePlaygroundRun();

    const [mode, setMode] = useState<SourceMode>("file");
    const [file, setFile] = useState<File | null>(null);
    const [fileUrl, setFileBlob] = useObjectUrl();
    const [url, setUrl] = useState("");
    const [chosenPresetId, setPresetId] = useState<number | null>(() => Number(searchParams.get("preset")) || null);
    const [customConfig, setCustomConfig] = useState<PresetConfig | null>(() => readPlaygroundState(location.state));
    const [engine, setEngine] = useState<ProcessingEngine>("preset");

    const presetId = chosenPresetId ?? presets.defaultPreset?.id ?? null;
    const preset = presets.presets.find(candidate => candidate.id === presetId) ?? null;

    const source: PlaygroundSource | null =
        mode === "file" ? (file ? { kind: "file", file } : null) : (isHttpUrl(url) ? { kind: "url", url: url.trim() } : null);
    const recipe: PlaygroundRecipe | null = customConfig
        ? { kind: "config", config: customConfig, engine }
        : presetId !== null ? { kind: "preset", presetId, engine } : null;
    const configValid = !customConfig || validatePresetConfig(customConfig).length === 0;

    const beforeUrl = mode === "file" ? fileUrl : source?.kind === "url" ? source.url : null;
    const beforeDimensions = useImageDimensions(beforeUrl);
    const afterDimensions = useImageDimensions(runner.resultUrl);

    function handleFile(next: File | null) {
        setFile(next);
        setFileBlob(next);
        runner.reset();
    }

    function handlePresetChange(id: number) {
        setPresetId(id);
        const next = presets.presets.find(candidate => candidate.id === id);
        // Keep tweaking, but start again from the newly chosen preset.
        if (customConfig && next) setCustomConfig(withDefaults(next.config));
    }

    function renderResult() {
        if (runner.running) {
            return (
                <div style={{ padding: 80, textAlign: "center" }}>
                    <Spin size="large" />
                    <Text type="secondary" style={{ display: "block", marginTop: 12 }}>Processing… the first run can take a while as models load.</Text>
                </div>
            );
        }
        if (runner.error) return <Alert type="error" showIcon title="Processing failed" description={runner.error} />;
        if (!runner.result || !runner.resultUrl) {
            return <Empty description="Pick an image and a preset, then run it to compare before and after." style={{ padding: 60 }} />;
        }
        const { result } = runner;
        return (
            <Space orientation="vertical" size={16} style={{ width: "100%" }}>
                <CompareView beforeUrl={beforeUrl} afterUrl={runner.resultUrl} />
                <ResultStats
                    originalBytes={file && mode === "file" ? file.size : null}
                    originalDimensions={beforeDimensions}
                    resultBytes={result.blob.size}
                    resultDimensions={afterDimensions}
                    resultType={result.blob.type}
                    processingMs={result.processingMs}
                />
                <Button type="primary" icon={<DownloadOutlined />} onClick={() => downloadBlob(result.blob, result.filename)}>
                    Download {result.filename}
                </Button>
            </Space>
        );
    }

    return (
        <PageContainer>
            <PageHeader
                icon={<ExperimentOutlined />} iconColor="#006A64" tint="#f0fdf4"
                title="Playground"
                subtitle="Run a preset on one image and compare the result. Nothing is written to the bucket."
            />
            <Row gutter={[24, 24]} align="top">
                <Col xs={24} xl={9}>
                    <Space orientation="vertical" size={16} style={{ width: "100%" }}>
                        <Card size="small" title="1. Image">
                            <SourcePicker
                                mode={mode} onModeChange={next => { setMode(next); runner.reset(); }}
                                file={file} onFileChange={handleFile}
                                url={url} onUrlChange={setUrl} disabled={runner.running}
                            />
                        </Card>
                        <Card size="small" title="2. Recipe">
                            <RecipePanel
                                presets={presets.presets} presetsLoading={presets.loading}
                                presetId={presetId} onPresetChange={handlePresetChange}
                                customConfig={customConfig}
                                onCustomize={on => setCustomConfig(on && preset ? withDefaults(preset.config) : null)}
                                onConfigChange={setCustomConfig}
                                engine={engine} onEngineChange={setEngine}
                            />
                        </Card>
                        <Button type="primary" size="large" block icon={<PlayCircleOutlined />} loading={runner.running}
                                disabled={!source || !recipe || !configValid}
                                onClick={() => source && recipe && void runner.run(source, recipe)}>
                            Run
                        </Button>
                        {presets.error && <Alert type="warning" showIcon title={presets.error} />}
                    </Space>
                </Col>
                <Col xs={24} xl={15}>
                    <Card size="small" title="Result" aria-live="polite">{renderResult()}</Card>
                </Col>
            </Row>
        </PageContainer>
    );
}
