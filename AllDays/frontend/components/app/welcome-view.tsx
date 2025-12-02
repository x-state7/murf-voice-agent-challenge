import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Button } from '@/components/livekit/button';

function ImprovIcon() {
  return (
    <svg
      width="90"
      height="90"
      viewBox="0 0 64 64"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className="mx-auto mb-8 drop-shadow-2xl"
      style={{
        background:
          'linear-gradient(135deg, #ff0000 0%, #ff7f00 14%, #ffff00 28%, #00ff00 42%, #0000ff 57%, #4b0082 71%, #9400d3 85%, #ff0000 100%)',
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
        backgroundClip: 'text',
      }}
    >
      <path
        d="M32 8C32 6.93913 31.5786 5.92172 30.8284 5.17157C30.0783 4.42143 29.0609 4 28 4C26.9391 4 25.9217 4.42143 25.1716 5.17157C24.4214 5.92172 24 6.93913 24 8V12C24 13.0609 24.4214 14.0783 25.1716 14.8284C25.9217 15.5786 26.9391 16 28 16H36C37.0609 16 38.0783 15.5786 38.8284 14.8284C39.5786 14.0783 40 13.0609 40 12V8C40 6.93913 39.5786 5.92172 38.8284 5.17157C38.0783 4.42143 37.0609 4 36 4C34.9391 4 33.9217 4.42143 33.1716 5.17157C32.4214 5.92172 32 6.93913 32 8ZM52 20H12C10.9391 20 9.92172 20.4214 9.17157 21.1716C8.42143 21.9217 8 22.9391 8 24V52C8 53.0609 8.42143 54.0783 9.17157 54.8284C9.92172 55.5786 10.9391 56 12 56H52C53.0609 56 54.0783 55.5786 54.8284 54.8284C55.5786 54.0783 56 53.0609 56 52V24C56 22.9391 55.5783 21.9217 54.8284 21.1716C54.0783 20.4214 53.0609 20 52 20ZM48 48H16V28H48V48Z"
        fill="currentColor"
      />
      <circle cx="22" cy="35" r="2" fill="currentColor" />
      <circle cx="32" cy="35" r="2" fill="currentColor" />
      <circle cx="42" cy="35" r="2" fill="currentColor" />
      <path
        d="M22 42C22 42 26 45 32 45C38 45 42 42 42 42"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

type WelcomeViewProps = {
  onStartCall: (name: string) => void;
};

export const WelcomeView = React.forwardRef<HTMLDivElement, WelcomeViewProps>((props, ref) => {
  const [name, setName] = useState('');
  const [started, setStarted] = useState(false);

  // rainbow keyframes for the button background
  useEffect(() => {
    const style = document.createElement('style');
    style.textContent = `
      @keyframes rainbow-shift {
        0% { background-position: 0% 50%; }
        100% { background-position: 200% 50%; }
      }
    `;
    document.head.appendChild(style);
    return () => {
      document.head.removeChild(style);
    };
  }, []);

  const handleStart = () => {
    if (!name.trim() || started) return;
    setStarted(true);
    setTimeout(() => {
      props.onStartCall(name.trim());
    }, 900);
  };

  return (
    <div
      ref={ref}
      className="relative flex min-h-screen w-full items-center justify-center overflow-hidden bg-black text-white"
    >
      {/* Rainbow background glow */}
      <div className="absolute inset-0 bg-gradient-to-br from-red-900/20 via-yellow-900/10 via-green-900/10 via-cyan-900/10 via-blue-900/10 to-purple-900/20" />

      <motion.div
        initial={{ opacity: 0, y: 30 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.8, type: 'spring', stiffness: 100 }}
        className="relative z-10 w-full max-w-md"
      >
        <div
          className="relative overflow-hidden rounded-3xl border border-transparent bg-black/80 p-12 shadow-2xl backdrop-blur-2xl"
          style={{
            borderImage:
              'linear-gradient(135deg, #ff0000, #ff7f00, #ffff00, #00ff00, #00ffff, #0000ff, #8b00ff) 1',
          }}
        >
          <ImprovIcon />

          <h2 className="mb-3 text-center text-5xl font-black tracking-tight">
            <span className="bg-gradient-to-r from-red-400 via-yellow-400 via-green-400 via-cyan-400 via-blue-400 to-purple-400 bg-clip-text text-transparent animate-pulse">
              Improv Battle
            </span>
          </h2>

          <p className="mb-10 text-center text-lg font-medium text-white/70">
            Enter your name to start the show
          </p>

          <div className="space-y-6">
            <div>
              <label className="mb-3 block text-center text-sm font-bold tracking-widest uppercase bg-gradient-to-r from-red-400 via-yellow-400 via-green-400 via-cyan-400 via-blue-400 to-purple-400 bg-clip-text text-transparent">
                Your Stage Name
              </label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleStart()}
                placeholder="Type your name..."
                className="w-full rounded-2xl border-2 bg-black/50 px-6 py-5 text-center text-lg font-semibold text-white backdrop-blur-xl transition-all placeholder:text-white/40 focus:ring-4 focus:outline-none"
                style={{
                  borderImage:
                    'linear-gradient(135deg, #ff0000, #ff7f00, #ffff00, #00ff00, #00ffff, #0000ff, #8b00ff) 1',
                  boxShadow: '0 0 20px rgba(255, 0, 255, 0.3)',
                }}
              />
            </div>

            <Button
              onClick={handleStart}
              disabled={!name.trim() || started}
              className="relative w-full overflow-hidden rounded-2xl bg-gradient-to-r from-red-500 via-yellow-500 via-green-500 via-cyan-500 via-blue-500 to-purple-500 py-6 text-2xl font-black tracking-wider text-white uppercase shadow-xl transition-all hover:scale-105 active:scale-95 disabled:opacity-50"
              style={{
                backgroundSize: '200% 100%',
                animation: 'rainbow-shift 3s linear infinite',
              } as React.CSSProperties}
            >
              <motion.div
                className="absolute inset-0 bg-white/20"
                animate={{ x: [-400, 400] }}
                transition={{ duration: 2.5, repeat: Infinity, ease: 'linear' }}
              />
              <span className="relative">{started ? 'Starting...' : "LET'S GO"}</span>
            </Button>
          </div>

          <p className="mt-8 text-center font-mono text-xs tracking-widest uppercase bg-gradient-to-r from-red-400 via-yellow-400 via-green-400 via-cyan-400 via-blue-400 to-purple-400 bg-clip-text text-transparent">
            Press Enter to continue
          </p>
        </div>
      </motion.div>

      {/* Clean loading screen */}
      {started && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="absolute inset-0 z-50 flex items-center justify-center bg-black/90 backdrop-blur-sm"
        >
          <div className="text-center">
            <p className="mb-4 animate-pulse text-4xl font-black drop-shadow-2xl bg-gradient-to-r from-red-400 via-yellow-400 via-green-400 via-cyan-400 via-blue-400 to-purple-400 bg-clip-text text-transparent">
              Getting things ready...
            </p>
            <p className="text-lg text-white/60">Preparing your improv scenarios</p>
          </div>
        </motion.div>
      )}
    </div>
  );
});

WelcomeView.displayName = 'WelcomeView';
