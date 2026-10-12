export const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api';
export async function api<T>(path: string, token: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(API + path, { ...init, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}), ...init.headers } });
    const body = await response.json().catch(() => null);
    if (!response.ok)
        throw new Error(typeof body?.detail === 'string' ? body.detail : `Request failed (${response.status})`);
    if (body === null)
        throw new Error('The server returned an invalid response. Try again.');
    return body as T;
}
export type Analysis = {
    summary: string;
    risks: string[];
    testing: string[];
    recommendations: string[];
};
export type Issue = {
    key: string;
    summary: string;
    status: string;
    priority: string;
    dependencies: string[];
    score?: number;
    explanation?: string;
    components?: Record<string, number>;
};
export type Result = {
    id: number;
    created_at: string;
    provider_id: string;
    analysis?: Analysis;
    progress?: number;
    distribution?: Record<string, number>;
    items?: (Issue & {
        issue_key?: string;
        kind?: string;
        certainty?: string;
        evidence?: string;
        recommendation?: string;
        pull_requests?: string[];
    })[];
    evidence: {
        title?: string;
        linked_issues?: string[];
        url?: string;
        files?: {
            filename: string;
            additions: number;
            deletions: number;
        }[];
        name?: string;
        issues?: Issue[];
    };
};
export type Activity = {
    id: number;
    workflow: string;
    source: string;
    status: string;
    attempts: number;
    created_at: string;
    error?: string;
    executions: {
        id: number;
        trace?: { nodes: { node: string; status: string; duration_ms: number }[]; integration_mode: string; llm_provider: string };
        duration_ms?: number;
        result?: Result;
        error?: string;
    }[];
};
