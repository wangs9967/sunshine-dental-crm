import { useEffect, useState } from 'react';
import { AdminRequestError } from './session';
import type { AdminSession } from './session';

export function useAdminRead<T>(session: AdminSession, path?: string, revision = 0) {
  const [attempt, setAttempt] = useState(0);
  const key = JSON.stringify([path, revision, attempt]);
  const [result, setResult] = useState<{
    key: string; session: AdminSession; data?: T; error?: string; expired?: boolean;
  }>();
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    session.read<T>(path, controller.signal).then(
      (data) => { if (!controller.signal.aborted) setResult({ key, session, data }); },
      (error: unknown) => {
        if (controller.signal.aborted) return;
        setResult({
          key, session,
          error: error instanceof AdminRequestError ? error.message : '读取失败，请重试。',
          expired: error instanceof AdminRequestError && error.status === 401,
        });
      },
    );
    return () => controller.abort();
  }, [session, path, key]);
  const current = result?.key === key && result.session === session ? result : undefined;
  return { data: current?.data, error: current?.error, expired: current?.expired, retry: () => setAttempt((n) => n + 1) };
}
