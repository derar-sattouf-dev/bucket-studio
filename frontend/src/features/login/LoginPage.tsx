import { useState } from "react";
import { App, Button, Form, Input, Typography } from "antd";
import { LockOutlined, UserOutlined } from "@ant-design/icons";
import { useNavigate } from "react-router-dom";
import { ApiError, getErrorMessage } from "../../api/client";
import { useAuth } from "../../auth/useAuth";
import { BrandLogo } from "../../components/BrandLogo";
import { APP_NAME, APP_TAGLINE } from "../../constants/app";

const { Text } = Typography;

interface Credentials {
    username: string;
    password: string;
}

function describeRetryAfter(seconds: number): string {
    if (seconds < 60) return `${seconds} second${seconds === 1 ? "" : "s"}`;
    const minutes = Math.ceil(seconds / 60);
    return `${minutes} minute${minutes === 1 ? "" : "s"}`;
}

function loginErrorMessage(error: unknown): string {
    if (error instanceof ApiError && error.status === 429) {
        const wait = error.retryAfterSeconds;
        return wait
            ? `Too many failed sign-in attempts. Try again in ${describeRetryAfter(wait)}.`
            : "Too many failed sign-in attempts. Please wait a few minutes and try again.";
    }
    if (error instanceof ApiError && error.status === 401) return "Invalid username or password";
    return getErrorMessage(error, "Sign-in failed");
}

const fieldLabel = (text: string) => <Text style={{ fontSize: 12, fontWeight: 600, color: "#475569" }}>{text}</Text>;

export default function LoginPage() {
    const [loading, setLoading] = useState(false);
    const { message } = App.useApp();
    const { login } = useAuth();
    const navigate = useNavigate();

    async function handleLogin({ username, password }: Credentials) {
        setLoading(true);
        try {
            await login(username, password);
            navigate("/");
        } catch (error) {
            message.error(loginErrorMessage(error));
        } finally {
            setLoading(false);
        }
    }

    return (
        <div style={{
            minHeight: "100vh",
            display: "flex", alignItems: "center", justifyContent: "center",
            background: "linear-gradient(135deg, #f0f9ff 0%, #f8fafc 50%, #f0fdf4 100%)",
        }}>
            <div style={{
                width: 380, background: "#fff",
                borderRadius: 18, border: "1px solid #e2e8f0",
                boxShadow: "0 8px 32px rgba(0,0,0,0.08)",
                overflow: "hidden",
            }}>
                <div style={{
                    background: "linear-gradient(135deg, #0B3B37 0%, #006A64 100%)",
                    padding: "28px 32px 24px",
                    textAlign: "center",
                }}>
                    <div style={{ display: "flex", justifyContent: "center", marginBottom: 12 }}>
                        <BrandLogo size={52} />
                    </div>
                    <h1 style={{ color: "#fff", fontSize: 20, fontWeight: 700, lineHeight: 1.2, margin: 0 }}>{APP_NAME}</h1>
                    <Text style={{ color: "rgba(255,255,255,0.75)", fontSize: 13 }}>{APP_TAGLINE}</Text>
                </div>

                <div style={{ padding: "28px 32px 32px" }}>
                    <Form<Credentials> layout="vertical" onFinish={handleLogin} requiredMark={false}>
                        <Form.Item name="username" label={fieldLabel("Username")} rules={[{ required: true }]}>
                            <Input
                                prefix={<UserOutlined style={{ color: "#94a3b8" }} />}
                                size="large" style={{ borderRadius: 8 }} autoFocus autoComplete="username"
                            />
                        </Form.Item>
                        <Form.Item name="password" label={fieldLabel("Password")} rules={[{ required: true }]}>
                            <Input.Password
                                prefix={<LockOutlined style={{ color: "#94a3b8" }} />}
                                size="large" style={{ borderRadius: 8 }} autoComplete="current-password"
                            />
                        </Form.Item>
                        <Form.Item style={{ marginBottom: 0, marginTop: 8 }}>
                            <Button
                                type="primary" htmlType="submit" loading={loading} block size="large"
                                style={{ borderRadius: 10, height: 44, fontWeight: 600, fontSize: 14 }}
                            >
                                Sign in
                            </Button>
                        </Form.Item>
                    </Form>
                </div>
            </div>
        </div>
    );
}
