import { useState } from "react";
import type { FaultInfo, SessionView } from "./api";
import { Header } from "./components/Header";
import { SessionScreen } from "./components/SessionScreen";
import { StartScreen } from "./components/StartScreen";

function App() {
  const [session, setSession] = useState<SessionView | null>(null);
  const [fault, setFault] = useState<FaultInfo | null>(null);

  return (
    <div className="min-h-screen">
      <Header />
      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
        {session && fault ? (
          <SessionScreen
            session={session}
            fault={fault}
            onSessionChange={setSession}
            onClosed={() => {
              setSession(null);
              setFault(null);
            }}
          />
        ) : (
          <StartScreen
            onStarted={(nextSession, nextFault) => {
              setSession(nextSession);
              setFault(nextFault);
            }}
          />
        )}
      </main>
    </div>
  );
}

export default App;
