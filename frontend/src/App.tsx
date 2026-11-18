import { useEffect, useState } from "react";
import {
  ApiError,
  getSession,
  listFaults,
  type FaultInfo,
  type ObservationResponse,
  type SessionView,
} from "./api";
import { ErrorBanner } from "./components/ErrorBanner";
import { SessionScreen } from "./components/SessionScreen";
import { StartScreen } from "./components/StartScreen";
import { TopBar } from "./components/TopBar";

/** Query parameter that keeps the open session across a page reload. */
export const SESSION_PARAM = "session";

function sessionIdFromUrl(): string | null {
  return new URLSearchParams(window.location.search).get(SESSION_PARAM);
}

function setSessionInUrl(sessionId: string | null): void {
  const url = new URL(window.location.href);
  if (sessionId) {
    url.searchParams.set(SESSION_PARAM, sessionId);
  } else {
    url.searchParams.delete(SESSION_PARAM);
  }
  window.history.replaceState(window.history.state, "", url);
}

function App() {
  const [session, setSession] = useState<SessionView | null>(null);
  const [fault, setFault] = useState<FaultInfo | null>(null);
  const [initial, setInitial] = useState<{
    observation: ObservationResponse | null;
    error: string | null;
  }>({ observation: null, error: null });
  const [restoring, setRestoring] = useState<boolean>(
    () => sessionIdFromUrl() !== null,
  );
  const [restoreError, setRestoreError] = useState<string | null>(null);

  useEffect(() => {
    const sessionId = sessionIdFromUrl();
    if (sessionId === null) {
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const [restored, faults] = await Promise.all([
          getSession(sessionId),
          listFaults(),
        ]);
        const restoredFault = faults.find(
          (item) => item.fault_id === restored.fault_id,
        );
        if (!restoredFault) {
          throw new Error(
            `Fault '${restored.fault_id}' for this session is no longer loaded.`,
          );
        }
        if (!cancelled) {
          setSession(restored);
          setFault(restoredFault);
        }
      } catch (err) {
        if (!cancelled) {
          setSessionInUrl(null);
          setRestoreError(
            `Could not reopen the session: ${
              err instanceof ApiError || err instanceof Error
                ? err.message
                : "request failed"
            }`,
          );
        }
      } finally {
        if (!cancelled) {
          setRestoring(false);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  if (restoring) {
    return (
      <div className="hud-glow min-h-screen">
        <TopBar />
        <p
          className="mx-auto max-w-content px-4 py-16 text-14 text-hud-muted sm:px-6"
          role="status"
        >
          Reopening session…
        </p>
      </div>
    );
  }

  return (
    <div className="hud-glow min-h-screen">
      {session && fault ? (
        <SessionScreen
          session={session}
          key={session.id}
          fault={fault}
          initialObservation={initial.observation}
          initialError={initial.error}
          onSessionChange={setSession}
          onClosed={() => {
            setSessionInUrl(null);
            setSession(null);
            setFault(null);
            setInitial({ observation: null, error: null });
          }}
        />
      ) : (
        <>
          <TopBar />
          <main className="mx-auto flex max-w-content flex-col items-stretch gap-4 px-4 py-16 sm:px-6">
            {restoreError ? (
              <ErrorBanner
                message={restoreError}
                onDismiss={() => setRestoreError(null)}
              />
            ) : null}
            <div className="flex items-start justify-center">
              <StartScreen
                onStarted={(nextSession, nextFault, nextInitial) => {
                  setSessionInUrl(nextSession.id);
                  setRestoreError(null);
                  setSession(nextSession);
                  setFault(nextFault);
                  setInitial(nextInitial);
                }}
              />
            </div>
          </main>
        </>
      )}
    </div>
  );
}

export default App;
