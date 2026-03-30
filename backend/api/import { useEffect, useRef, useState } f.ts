import { useEffect, useRef, useState } from "react";
import React from "react";
import { Mic } from "@/components/icons";
import { useSpeechRecognition } from "@/hooks/useSpeechRecognition";

type UseSpeechRecognitionOptions = {
  language?: string;
  continuous?: boolean;
  interimResults?: boolean;
  onResult?: (text: string) => void;
};

export function useSpeechRecognition(options: UseSpeechRecognitionOptions = {}) {
  const { language = "zh-CN", continuous = true, interimResults = true, onResult } = options;
  const [isSupported, setIsSupported] = useState(false);
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  useEffect(() => {
    const windowAny = window as any;
    const SpeechRecognition =
      windowAny.SpeechRecognition || windowAny.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      setIsSupported(false);
      setError("当前浏览器不支持 Web Speech API");
      return;
    }

    setIsSupported(true);
    const recognition: SpeechRecognition = new SpeechRecognition();
    recognition.continuous = continuous;
    recognition.interimResults = interimResults;
    recognition.lang = language;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let text = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const result = event.results[i];
        text += result[0].transcript;
      }

      if (onResult) onResult(text);
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (event.error === "not-allowed" || event.error === "permission-denied") {
        setError("麦克风权限未授权，请允许访问麦克风");
      } else if (event.error === "no-speech" || event.error === "aborted") {
        setError("未检测到语音，请重试");
      } else {
        setError("语音识别错误：" + event.error);
      }
      setListening(false);
    };

    recognition.onend = () => {
      setListening(false);
    };

    recognitionRef.current = recognition;
    return () => {
      recognition.stop?.();
      recognitionRef.current = null;
    };
  }, [language, continuous, interimResults, onResult]);

  const start = () => {
    if (!isSupported || !recognitionRef.current) {
      setError("语音识别不支持");
      return;
    }
    setError(null);
    try {
      recognitionRef.current.start();
      setListening(true);
    } catch (e) {
      setError("语音识别启动失败");
      setListening(false);
    }
  };

  const stop = () => {
    if (!recognitionRef.current) return;
    recognitionRef.current.stop();
    setListening(false);
  };

  const toggle = () => {
    if (listening) stop();
    else start();
  };

  return {
    isSupported,
    listening,
    error,
    start,
    stop,
    toggle,
  };
}

const DashboardView = () => {
  const [inputValue, setInputValue] = React.useState("");
  const { isSupported, listening, error, toggle } = useSpeechRecognition({
    onResult: (text) => {
      if (!text) return;
      // 追加至原输入，可替换为覆盖：setInputValue(text);
      setInputValue((prev) => (prev ? `${prev} ${text}` : text));
    },
  });

  return (
    <div className="chat-input-wrap">
      <textarea
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        placeholder="请输入内容..."
      />
      <button
        type="button"
        aria-label="语音输入"
        onClick={() => {
          if (!isSupported) {
            window.alert("浏览器不支持语音识别，请换用 Chrome/Edge/Safari");
            return;
          }
          toggle();
        }}
      >
        <Mic className={listening ? "mic-active" : ""} />
      </button>
      {error && <div className="speech-error">{error}</div>}
    </div>
  );
};

export default DashboardView;