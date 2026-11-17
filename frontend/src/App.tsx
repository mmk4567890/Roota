import { useState } from "react";
import type { FaultInfo, ObservationResponse, SessionView } from "./api";
import { SessionScreen } from "./components/SessionScreen";
import { StartScreen } from "./components/StartScreen";
import { TopBar } from "./components/TopBar";

function App() {
  const [session, setSession] = useState<SessionView | null>(null);
  const [fault, setFault] = useState<FaultInfo | null>(null);
  const [initial, setInitial] = useState<{
    observation: ObservationResponse | null;
    error: string | null;
  }>({ observation: null, error: null });

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
            setSession(null);
            setFault(null);
            setInitial({ observation: null, error: null });
          }}
        />
      ) : (
        <>
          <TopBar />
          <main className="mx-auto flex max-w-content items-start justify-center px-4 py-16 sm:px-6">
            <StartScreen
              onStarted={(nextSession, nextFault, nextInitial) => {
                setSession(nextSession);
                setFault(nextFault);
                setInitial(nextInitial);
              }}
            />
          </main>
        </>
      )}
    </div>
  );
}

export default App;
