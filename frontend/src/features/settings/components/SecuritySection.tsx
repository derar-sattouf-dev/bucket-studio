import { Card, Col, InputNumber, Row } from "antd";
import { Field } from "../../../components/Field";
import { humanizeMinutes } from "../../../utils/format";
import type { AdminSettingsState } from "../hooks/useAdminSettings";

const FULL = { width: "100%" } as const;

export function SecuritySection({ admin }: { admin: AdminSettingsState }) {
    const { values, editing, update } = admin;
    return (
        <Card size="small" title="Sign-in & sessions" style={{ borderRadius: 12 }}>
            <Row gutter={[24, 20]}>
                <Col xs={24} md={8}>
                    <Field htmlFor="session-minutes" label="Session length (minutes)"
                           help={`${humanizeMinutes(values.session_minutes)}. Users sign in again after this (5 min – 7 d). Applies to new sessions.`}>
                        <InputNumber id="session-minutes" min={5} max={10080} step={60} value={values.session_minutes}
                                     disabled={!editing} style={FULL}
                                     onChange={value => value !== null && update({ session_minutes: value })} />
                    </Field>
                </Col>
                <Col xs={24} md={8}>
                    <Field htmlFor="login-attempts" label="Failed sign-ins before lockout"
                           help="Per IP address and user name (1–100).">
                        <InputNumber id="login-attempts" min={1} max={100} value={values.login_max_attempts}
                                     disabled={!editing} style={FULL}
                                     onChange={value => value !== null && update({ login_max_attempts: value })} />
                    </Field>
                </Col>
                <Col xs={24} md={8}>
                    <Field htmlFor="lockout-minutes" label="Lockout (minutes)"
                           help={`${humanizeMinutes(values.login_lockout_minutes)}. How long sign-in stays blocked after too many failures.`}>
                        <InputNumber id="lockout-minutes" min={1} max={1440} value={values.login_lockout_minutes}
                                     disabled={!editing} style={FULL}
                                     onChange={value => value !== null && update({ login_lockout_minutes: value })} />
                    </Field>
                </Col>
            </Row>
        </Card>
    );
}
