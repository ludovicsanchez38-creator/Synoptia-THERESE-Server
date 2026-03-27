import { useState, useRef, useCallback, useEffect } from "react";
import { transcribeAudio, isMediaRecorderSupported } from "../../services/api/voiceService";

interface VoiceRecorderProps {
  /** Callback appelé avec le texte transcrit */
  onTranscription: (text: string) => void;
  /** Désactiver le bouton (ex: pas de conversation active) */
  disabled?: boolean;
}

type RecorderState = "idle" | "recording" | "transcribing";

export default function VoiceRecorder({ onTranscription, disabled = false }: VoiceRecorderProps) {
  const [state, setState] = useState<RecorderState>("idle");
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Vérifier le support navigateur
  const isSupported = isMediaRecorderSupported();

  // Cleanup au démontage
  useEffect(() => {
    return () => {
      stopTimer();
      stopStream();
    };
  }, []);

  const stopTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const stopStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
  }, []);

  const formatDuration = (seconds: number): string => {
    const m = Math.floor(seconds / 60);
    const s = seconds % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  const startRecording = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // Choisir le format supporté
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : MediaRecorder.isTypeSupported("audio/webm")
        ? "audio/webm"
        : "audio/mp4";

      const mediaRecorder = new MediaRecorder(stream, { mimeType });
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) {
          chunksRef.current.push(e.data);
        }
      };

      mediaRecorder.onstop = async () => {
        stopTimer();
        stopStream();

        const audioBlob = new Blob(chunksRef.current, { type: mimeType });
        if (audioBlob.size === 0) {
          setState("idle");
          setError("Enregistrement vide");
          return;
        }

        setState("transcribing");
        try {
          const result = await transcribeAudio(audioBlob);
          if (result.text) {
            onTranscription(result.text);
          } else {
            setError("Aucun texte détecté");
          }
        } catch (err) {
          const msg = err instanceof Error ? err.message : "Erreur de transcription";
          setError(msg);
        } finally {
          setState("idle");
          setDuration(0);
        }
      };

      mediaRecorder.onerror = () => {
        stopTimer();
        stopStream();
        setState("idle");
        setError("Erreur d'enregistrement");
      };

      mediaRecorder.start(250); // chunks toutes les 250ms
      setState("recording");
      setDuration(0);

      timerRef.current = setInterval(() => {
        setDuration((d) => d + 1);
      }, 1000);
    } catch (err) {
      stopStream();
      if (err instanceof DOMException && err.name === "NotAllowedError") {
        setError("Permission micro refusée");
      } else if (err instanceof DOMException && err.name === "NotFoundError") {
        setError("Aucun microphone détecté");
      } else {
        setError("Impossible d'accéder au micro");
      }
    }
  }, [onTranscription, stopTimer, stopStream]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
    }
  }, []);

  const handleClick = useCallback(() => {
    if (state === "recording") {
      stopRecording();
    } else if (state === "idle") {
      startRecording();
    }
    // Pendant "transcribing", on ne fait rien
  }, [state, startRecording, stopRecording]);

  // Masquer si le navigateur ne supporte pas
  if (!isSupported) {
    return null;
  }

  return (
    <div className="relative flex items-center gap-1.5">
      {/* Indicateur de durée pendant l'enregistrement */}
      {state === "recording" && (
        <span className="text-xs text-red-400 font-mono tabular-nums animate-pulse">
          {formatDuration(duration)}
        </span>
      )}

      {/* Indicateur de transcription */}
      {state === "transcribing" && (
        <span className="text-xs text-[var(--color-cyan)] animate-pulse">
          Transcription...
        </span>
      )}

      {/* Bouton micro */}
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled || state === "transcribing"}
        title={
          state === "recording"
            ? "Arrêter l'enregistrement"
            : state === "transcribing"
            ? "Transcription en cours..."
            : "Enregistrer un message vocal"
        }
        aria-label={
          state === "recording"
            ? "Arrêter l'enregistrement"
            : "Enregistrer un message vocal"
        }
        className={`
          p-2.5 rounded-xl transition-all duration-200 shrink-0
          ${
            state === "recording"
              ? "bg-red-500 hover:bg-red-600 text-white animate-pulse shadow-lg shadow-red-500/30"
              : state === "transcribing"
              ? "bg-slate-700 text-[var(--color-muted)] cursor-wait opacity-60"
              : "bg-slate-800/70 border border-slate-700 hover:border-[var(--color-primary)]/50 text-[var(--color-muted)] hover:text-[var(--color-text)]"
          }
          disabled:opacity-30 disabled:cursor-not-allowed
        `}
      >
        {state === "transcribing" ? (
          /* Spinner */
          <svg
            className="animate-spin"
            xmlns="http://www.w3.org/2000/svg"
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M21 12a9 9 0 1 1-6.219-8.56" />
          </svg>
        ) : (
          /* Icône micro */
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="18"
            height="18"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" x2="12" y1="19" y2="22" />
          </svg>
        )}
      </button>

      {/* Message d'erreur flottant */}
      {error && (
        <div className="absolute bottom-full right-0 mb-2 px-3 py-1.5 bg-red-500/20 border border-red-500/30 rounded-lg text-xs text-red-400 whitespace-nowrap z-50">
          {error}
          <button
            type="button"
            onClick={() => setError(null)}
            className="ml-2 text-red-300 hover:text-white"
            aria-label="Fermer l'erreur"
          >
            x
          </button>
        </div>
      )}
    </div>
  );
}
