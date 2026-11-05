import { useState } from "react";
import type { FaultInfo, ObservationResponse, SessionView } from "./api";
import { Header } from "./components/Header";
import { SessionScreen } from "./components/SessionScreen";
import { StartScreen } from "./components/StartScreen";

function App() {
  const [session, setSession] = useState<SessionView | null>(null);
  const [fault, setFault] = useState<FaultInfo | null>(null);
  const [initial, setInitial] = useState<{
    observation: ObservationResponse | null;
    error: string | null;
  }>({ observation: null, error: null });

  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
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
            }}
          />
        ) : (
          <StartScreen
            onStarted={(nextSession, nextFault, nextInitial) => {
              setSession(nextSession);
              setFault(nextFault);
              setInitial(nextInitial);
            }}
          />
        )}
      </main>
    </div>
  );
}

export default App;
