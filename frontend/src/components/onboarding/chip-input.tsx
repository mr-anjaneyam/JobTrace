import { useRef, useState, type KeyboardEvent } from 'react';
import { X } from 'lucide-react';

export function ChipInput({
  value,
  onChange,
  suggestions = [],
  placeholder,
  max = 20,
  id,
}: {
  value: string[];
  onChange: (next: string[]) => void;
  suggestions?: string[];
  placeholder?: string;
  max?: number;
  id?: string;
}) {
  const [text, setText] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const has = (v: string) => value.some((x) => x.toLowerCase() === v.toLowerCase());

  const add = (raw: string) => {
    const v = raw.replace(/,+$/, '').trim();
    setText('');
    if (!v || has(v) || value.length >= max) return;
    onChange([...value, v]);
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if ((e.key === 'Enter' || e.key === ',') && text.trim()) {
      e.preventDefault();
      add(text);
    } else if (e.key === 'Backspace' && !text && value.length) {
      onChange(value.slice(0, -1));
    }
  };

  const rest = suggestions.filter((s) => !has(s));

  return (
    <div className="ob-chips">
      <div className="ob-chip-field" onClick={() => inputRef.current?.focus()}>
        {value.map((v) => (
          <span className="ob-chip" key={v}>
            {v}
            <button type="button" aria-label={`Remove ${v}`} onClick={() => onChange(value.filter((x) => x !== v))}>
              <X size={11} />
            </button>
          </span>
        ))}
        <input
          id={id}
          ref={inputRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={onKeyDown}
          onBlur={() => text.trim() && add(text)}
          placeholder={value.length ? '' : placeholder}
          autoComplete="off"
        />
      </div>
      {rest.length > 0 && (
        <div className="ob-suggest">
          {rest.map((s) => (
            <button type="button" className="ob-suggest-chip" key={s} onClick={() => add(s)}>
              + {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
