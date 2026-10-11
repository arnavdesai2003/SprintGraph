'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from 'recharts';
import { GitPullRequest, LayoutDashboard, ListOrdered, Activity as ActivityIcon, Settings, Layers, ArrowUpRight, Workflow, LogOut } from 'lucide-react';
import { api, type Result, type Activity } from './api';
import { Button } from './ui/button';
const navigation = [['/', 'Overview', LayoutDashboard], ['/pull-requests', 'Pull Requests', GitPullRequest], ['/sprint-insights', 'Sprint Insights', Layers], ['/task-priorities', 'Task Priorities', ListOrdered], ['/workflow-activity', 'Workflow Activity', ActivityIcon], ['/settings', 'Settings', Settings]] as const;
type Overview = {
    total_events: number;
    statuses: Record<string, number>;
    p50_latency_ms: number | null;
    p95_latency_ms: number | null;
    automated_events: number;
    measurement_mode: string;
};
type Config = {
    mode: string;
    llm_provider: string;
    llm_model: string;
    github_configured: boolean;
    jira_configured: boolean;
    external_actions: string;
    users: {
        id: number;
        email: string;
        role: string;
    }[];
};
function AnalysisView({ result }: {
    result: Result;
}) { return <><p className="leading-relaxed text-slate-300">{result.analysis?.summary}</p>{(['risks', 'testing', 'recommendations'] as const).map(k => result.analysis?.[k]?.length ? <div key={k} className="mt-4"><h3 className="text-xs uppercase tracking-wider text-teal-300">{k}</h3><ul className="mt-2 list-inside list-disc space-y-1 text-sm text-slate-400">{result.analysis[k].map((v, i) => <li key={i}>{v}</li>)}</ul></div> : null)}</>; }
function Evidence({ result }: {
    result: Result;
}) { return <details className="mt-4 text-sm text-slate-400"><summary className="cursor-pointer">Inspect source evidence</summary><pre className="mt-3 rounded-lg bg-slate-950 p-3 text-xs">{JSON.stringify(result.evidence, null, 2)}</pre></details>; }
export function Dashboard({ page }: {
    page: string;
}) {
    const [token, setToken] = useState('');
    const [email, setEmail] = useState('admin@sprintgraph.local');
    const [password, setPassword] = useState('');
    const [message, setMessage] = useState('');
    const [selected, setSelected] = useState(0);
    const [prNumber, setPrNumber] = useState(42);
    const pathname = usePathname();
    const qc = useQueryClient();
    useEffect(() => { setToken(sessionStorage.getItem('sprintgraph-token') || ''); }, []);
    const auth = useQuery({ queryKey: ['me', token], queryFn: () => api<{
            email: string;
            role: string;
        }>('/auth/me', token), enabled: !!token, retry: false });
    const projects = useQuery({ queryKey: ['projects', token], queryFn: () => api<{
            id: number;
            name: string;
        }[]>('/projects', token), enabled: !!auth.data });
    const project = selected || projects.data?.[0]?.id || 0;
    const enabled = !!auth.data && !!project;
    const overview = useQuery({ queryKey: ['overview', token, project], queryFn: () => api<Overview>(`/projects/${project}/overview`, token), enabled });
    const activity = useQuery({ queryKey: ['activity', token, project], queryFn: () => api<Activity[]>(`/projects/${project}/activity`, token), enabled });
    const prs = useQuery({ queryKey: ['prs', token, project], queryFn: () => api<Result[]>(`/projects/${project}/results/pull_request`, token), enabled });
    const sprints = useQuery({ queryKey: ['sprints', token, project], queryFn: () => api<Result[]>(`/projects/${project}/results/sprint_summary`, token), enabled });
    const blockers = useQuery({ queryKey: ['blockers', token, project], queryFn: () => api<Result[]>(`/projects/${project}/results/blockers`, token), enabled });
    const priorities = useQuery({ queryKey: ['priorities', token, project], queryFn: () => api<Result[]>(`/projects/${project}/results/priorities`, token), enabled });
    const config = useQuery({ queryKey: ['settings', token], queryFn: () => api<Config>('/settings', token), enabled: !!auth.data && page === 'settings' && auth.data.role === 'admin' });
    const audit = useQuery({ queryKey: ['audit', token], queryFn: () => api<{
            id: number;
            action: string;
            created_at: string;
            details: object;
        }[]>('/audit', token), enabled: !!config.data });
    const run = useMutation({ mutationFn: (workflow: string) => api<{
            event_id: number;
        }>(`/projects/${project}/run`, token, { method: 'POST', body: JSON.stringify({ workflow, number: prNumber }) }), onSuccess: data => { setMessage(`Event #${data.event_id} queued. Results refresh automatically.`); qc.invalidateQueries(); }, onError: e => setMessage(e.message) });
    const roleChange = useMutation({ mutationFn: ({ id, role }: {
            id: number;
            role: string;
        }) => api(`/users/${id}/role`, token, { method: 'PATCH', body: JSON.stringify({ role, confirmed: true }) }), onSuccess: () => { setMessage('Permission change saved and audited.'); qc.invalidateQueries(); }, onError: e => setMessage(e.message) });
    async function signIn(e: React.FormEvent) { e.preventDefault(); try {
        const data = await api<{
            access_token: string;
        }>('/auth/login', '', { method: 'POST', body: JSON.stringify({ email, password }) });
        sessionStorage.setItem('sprintgraph-token', data.access_token);
        setToken(data.access_token);
        setPassword('');
        setMessage('');
    }
    catch (e) {
        setMessage((e as Error).message);
    } }
    function signOut() { sessionStorage.removeItem('sprintgraph-token'); setToken(''); setSelected(0); qc.clear(); }
    const failures = [projects.error, overview.error, activity.error, prs.error, sprints.error, blockers.error, priorities.error, config.error].filter(Boolean);
    if (!token || auth.isError)
        return <main className="flex min-h-screen items-center justify-center p-6"><form onSubmit={signIn} className="panel w-full max-w-md space-y-5"><Workflow className="text-teal-300" size={36}/><h1 className="text-2xl font-bold">Welcome to SprintGraph</h1><p className="text-sm text-slate-400">Sign in with a seeded account and DEMO_PASSWORD from your private .env file.</p><label className="block text-sm">Email<input className="mt-2 w-full" type="email" value={email} onChange={e => setEmail(e.target.value)} required autoComplete="username"/></label><label className="block text-sm">Password<input className="mt-2 w-full" type="password" value={password} onChange={e => setPassword(e.target.value)} required autoComplete="current-password"/></label><Button className="w-full">Sign in</Button>{(message || auth.isError) && <p role="alert" className="text-sm text-rose-300">{message || 'Session expired. Sign in again.'}</p>}</form></main>;
    const sprint = sprints.data?.[0];
    const findings = blockers.data?.[0]?.items || [];
    const workflow = page === 'pull-requests' ? 'pull_request' : page === 'sprint-insights' ? 'sprint_summary' : page === 'task-priorities' ? 'priorities' : 'blockers';
    return <div className="min-h-screen md:flex"><aside className="border-b border-slate-800 bg-slate-950/50 p-5 md:fixed md:inset-y-0 md:w-60 md:border-r"><Link href="/" className="mb-8 flex items-center gap-3 text-xl font-semibold"><Workflow className="text-teal-300"/>SprintGraph</Link><p className="mb-3 text-[10px] uppercase tracking-[.2em] text-slate-500">Engineering workspace</p><nav className="flex flex-wrap gap-1 md:flex-col">{navigation.map(([url, label, Icon]) => <Link key={url} href={url} className={`flex items-center gap-3 rounded-lg px-3 py-3 text-sm ${pathname === url ? 'bg-teal-400/10 text-teal-300' : 'text-slate-400 hover:bg-slate-800'}`}><Icon size={18}/>{label}</Link>)}</nav><div className="mt-8 text-xs text-slate-500">Advisory AI · Auditable workflows<br />Demo metrics are labeled separately</div></aside><main className="min-w-0 flex-1 p-5 md:ml-60 md:p-9"><header className="mb-9 flex flex-wrap items-center justify-between gap-4"><div><p className="mb-2 text-xs uppercase tracking-widest text-teal-300">Engineering intelligence</p><h1 className="text-3xl font-semibold">{navigation.find(([url]) => url === pathname)?.[1] || 'Overview'}</h1></div><div className="flex items-center gap-3"><select aria-label="Project" value={project} onChange={e => setSelected(Number(e.target.value))}>{projects.data?.map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select><Button aria-label="Sign out" variant="outline" size="sm" onClick={signOut}><LogOut size={16}/></Button></div></header><div className="mb-5 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-500"><span>{auth.data?.email} · {auth.data?.role}</span><span className="rounded-full border border-teal-900 bg-teal-950/50 px-3 py-1 text-teal-300">{overview.data?.measurement_mode || 'Connecting'} environment</span></div>{message && <p role="status" className="panel mb-5 text-sm text-teal-200">{message}</p>}{failures.map((e, i) => <p role="alert" className="panel mb-3 text-rose-300" key={i}>{e?.message}</p>)}{(auth.isLoading || projects.isLoading || overview.isLoading) && <p className="panel animate-pulse">Loading workspace…</p>}{projects.data?.length === 0 && <p className="panel">No projects available. Run the demo seed command.</p>}
  {page === 'overview' && <><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{[['Engineering events', overview.data?.total_events || 0], ['Successful workflows', overview.data?.statuses.succeeded || 0], ['Failed workflows', overview.data?.statuses.failed || 0], ['Blocker findings', findings.length]].map(([label, value]) => <div className="panel" key={label}><p className="text-sm text-slate-400">{label}</p><p className="mt-4 text-3xl font-semibold">{value}</p></div>)}</div><div className="mt-6 grid gap-6 lg:grid-cols-2"><section className="panel"><h2 className="mb-5 font-medium">Sprint status</h2>{sprint ? <><p className="mb-3 text-sm text-slate-400">{sprint.evidence.name} · {Math.round((sprint.progress || 0) * 100)}% complete</p><Chart distribution={sprint.distribution || {}}/></> : <Empty />}</section><section className="panel"><h2 className="mb-5 font-medium">Processing latency</h2><p className="text-sm text-slate-400">Measured from ingestion through final completion, including queue wait and retries.</p><div className="mt-8 grid grid-cols-2 gap-4">{[['P50', overview.data?.p50_latency_ms], ['P95', overview.data?.p95_latency_ms]].map(([k, v]) => <div key={String(k)}><p className="text-xs text-slate-500">{k}</p><p className="mt-2 text-2xl">{typeof v === 'number' ? `${(v / 1000).toFixed(2)}s` : '—'}</p></div>)}</div><p className="mt-6 text-xs text-slate-500">Local demo measurements; no historical automation claim is asserted.</p></section></div><section className="panel mt-6"><h2 className="mb-4 font-medium">Recent automation activity</h2><ActivityTable items={activity.data?.slice(0, 6) || []}/></section></>}
  {page !== 'overview' && page !== 'settings' && <div className="mb-6 flex flex-wrap gap-3">{page === 'pull-requests' && <input aria-label="PR number" type="number" min={1} value={prNumber} onChange={e => setPrNumber(Number(e.target.value))}/>}<Button disabled={!enabled || run.isPending || prNumber < 1} onClick={() => run.mutate(workflow)}>Run {workflow.replaceAll('_', ' ')} <ArrowUpRight size={16} className="ml-2"/></Button>{page === 'sprint-insights' && <Button variant="outline" disabled={run.isPending} onClick={() => run.mutate('blockers')}>Refresh blockers</Button>}</div>}
  {page === 'pull-requests' && <div className="space-y-5">{prs.data?.length ? prs.data.map(r => <article key={r.id} className="panel"><div className="mb-4 flex items-start justify-between gap-4"><h2 className="font-semibold">{r.evidence.title}</h2><a href={r.evidence.url} target="_blank" rel="noreferrer" className="text-xs text-teal-300">View PR ↗</a></div><div className="mb-4 flex gap-2">{r.evidence.linked_issues?.map(k => <span className="rounded bg-slate-800 px-2 py-1 text-xs" key={k}>{k}</span>)}</div><AnalysisView result={r}/><Evidence result={r}/></article>) : <Empty />}</div>}
  {page === 'sprint-insights' && <><section className="panel">{sprint ? <><h2 className="mb-4 font-semibold">{sprint.evidence.name}</h2><AnalysisView result={sprint}/><Chart distribution={sprint.distribution || {}}/><Evidence result={sprint}/></> : <Empty />}</section><section className="panel mt-6"><h2 className="mb-4 font-semibold">Blockers and signals</h2>{blockers.data?.[0] && <AnalysisView result={blockers.data[0]}/>}{findings.length ? findings.map((f, i) => <div className="border-t border-slate-800 py-4" key={i}><div className="flex gap-3"><span className="font-medium">{f.issue_key}</span><span className={`text-xs ${f.certainty === 'definite' ? 'text-rose-300' : 'text-amber-300'}`}>{f.certainty} · {f.kind}</span></div><p className="mt-2 text-sm text-slate-400">{String(f.evidence)}</p><p className="mt-1 text-sm text-teal-200">{f.recommendation}</p>{f.pull_requests?.map(url => <a key={url} className="mr-3 text-xs text-teal-300" href={url}>Related PR ↗</a>)}</div>) : <Empty />}</section></>}
  {page === 'task-priorities' && <section className="panel"><p className="mb-5 text-sm text-slate-400">Deterministic scores. Model explanations cannot change ranking or grant permissions.</p>{priorities.data?.[0]?.items?.map((issue, i) => <div key={issue.key} className="flex gap-4 border-t border-slate-800 py-5"><span className="text-xl text-slate-600">{String(i + 1).padStart(2, '0')}</span><div className="flex-1"><h2 className="font-medium">{issue.key} · {issue.summary}</h2><p className="mt-2 text-sm text-slate-400">{issue.explanation}</p><p className="mt-2 text-xs text-slate-500">{issue.status} · Dependencies: {issue.dependencies.join(', ') || 'None'}</p></div><span className="text-2xl text-teal-300">{issue.score}</span></div>)}{!priorities.data?.length && <Empty />}{priorities.data?.[0] && <Evidence result={priorities.data[0]}/>}</section>}
  {page === 'workflow-activity' && <section className="panel"><ActivityTable items={activity.data || []} detailed/></section>}
  {page === 'settings' && <>{auth.data?.role !== 'admin' ? <p className="panel">Settings require the Admin role.</p> : <div className="space-y-6"><section className="panel"><h2 className="mb-4 font-semibold">Integration configuration</h2><p className="text-sm text-slate-400">Credentials are managed through environment variables. Secret values are never returned by the API.</p><dl className="mt-5 grid grid-cols-2 gap-4 text-sm">{[['Mode', config.data?.mode], ['GitHub', config.data?.github_configured ? 'Configured' : 'Demo / credentials missing'], ['Jira', config.data?.jira_configured ? 'Configured' : 'Demo / credentials missing'], ['AI provider', `${config.data?.llm_provider || '…'} · ${config.data?.llm_model || ''}`]].map(([k, v]) => <div key={k}><dt className="text-slate-500">{k}</dt><dd className="mt-1">{v}</dd></div>)}</dl><p className="mt-5 text-xs text-teal-300">{config.data?.external_actions}</p></section><section className="panel"><h2 className="mb-4 font-semibold">User permissions</h2>{config.data?.users.map(u => <div className="flex items-center justify-between border-t border-slate-800 py-4 text-sm" key={u.id}><span>{u.email}</span><div className="flex items-center gap-3"><span>{u.role}</span>{u.email !== auth.data?.email && <Button size="sm" variant="outline" disabled={roleChange.isPending} onClick={() => { const role = u.role === 'admin' ? 'developer' : 'admin'; if (window.confirm(`Change ${u.email} to ${role}? This changes access to settings, audit logs and user permissions.`))
        roleChange.mutate({ id: u.id, role }); }}>Change role</Button>}</div></div>)}<p className="mt-4 text-xs text-slate-500">Role changes use the admin-only API and are audited.</p></section><section className="panel"><h2 className="mb-4 font-semibold">Audit trail</h2>{audit.data?.slice(0, 20).map(a => <details key={a.id} className="border-t border-slate-800 py-3 text-sm"><summary>{a.action} · {new Date(a.created_at).toLocaleString()}</summary><pre className="mt-2 text-xs text-slate-400">{JSON.stringify(a.details, null, 2)}</pre></details>)}</section></div>}</>}
  </main></div>;
}
function Empty() { return <p className="py-6 text-sm text-slate-500">No results yet. Run a workflow or load demo data.</p>; }
function Chart({ distribution }: {
    distribution: Record<string, number>;
}) { return <div className="mt-4 h-60"><ResponsiveContainer width="100%" height="100%"><BarChart data={Object.entries(distribution).map(([name, count]) => ({ name, count }))}><CartesianGrid stroke="#1e293b" vertical={false}/><XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 11 }}/><YAxis allowDecimals={false} tick={{ fill: '#94a3b8', fontSize: 11 }}/><Tooltip contentStyle={{ background: '#0f172a', borderColor: '#334155' }}/><Bar dataKey="count" fill="#2dd4bf" radius={[4, 4, 0, 0]}/></BarChart></ResponsiveContainer></div>; }
function ActivityTable({ items, detailed = false }: {
    items: Activity[];
    detailed?: boolean;
}) { return items.length ? <div className="space-y-3">{items.map(a => <details key={a.id} className="rounded-lg border border-slate-800 p-4"><summary className="flex cursor-pointer flex-wrap items-center justify-between gap-3 text-sm"><span>#{a.id} · {a.workflow.replaceAll('_', ' ')}</span><span className={a.status === 'succeeded' ? 'text-teal-300' : a.status === 'failed' ? 'text-rose-300' : 'text-amber-300'}>{a.status}</span><span className="text-xs text-slate-500">{new Date(a.created_at).toLocaleString()}</span></summary><div className="mt-4 text-xs text-slate-400">Source: {a.source} · Attempts: {a.attempts}{a.error && <p className="mt-2 text-rose-300">{a.error}</p>}{detailed && a.executions.map(e => <div key={e.id} className="mt-3"><p>Execution #{e.id} · {e.duration_ms?.toFixed(0)} ms</p><pre className="mt-2">{JSON.stringify(e.result || { error: e.error }, null, 2)}</pre></div>)}</div></details>)}</div> : <Empty />; }
