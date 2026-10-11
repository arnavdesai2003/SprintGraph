import './globals.css';
import { Providers } from '@/components/providers';
export const metadata = { title: 'SprintGraph · Engineering Intelligence', description: 'Auditable engineering workflow automation' };
export default function Layout({ children }: {
    children: React.ReactNode;
}) { return <html lang="en"><body><Providers>{children}</Providers></body></html>; }
