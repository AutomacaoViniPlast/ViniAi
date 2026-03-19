import { useEffect, useState } from "react";

/**
 * Cache global em memória.
 * Sobrevive a re-render.
 * Não depende de useRef do componente.
 */
const animatedMessages = new Set<string>();

export const useTypewriter = (
  id: string,
  text: string,
  speed: number = 8
) => {
  const alreadyAnimated = animatedMessages.has(id);

  const [displayed, setDisplayed] = useState(
    alreadyAnimated ? text : ""
  );
  const [isDone, setIsDone] = useState(alreadyAnimated);

  useEffect(() => {
    if (alreadyAnimated) return;

    let index = 0;

    const interval = setInterval(() => {
      index++;
      setDisplayed(text.slice(0, index));

      if (index >= text.length) {
        clearInterval(interval);
        setIsDone(true);
        animatedMessages.add(id); // 🔥 Marca como animado globalmente
      }
    }, speed);

    return () => clearInterval(interval);
  }, [id, text, speed, alreadyAnimated]);

  return { displayed, isDone };
};