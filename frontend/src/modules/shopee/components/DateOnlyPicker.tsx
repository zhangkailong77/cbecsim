import { Calendar, ChevronLeft, ChevronRight } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';

export interface DateOnlyPickerProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

function pad2(num: number): string {
  return String(num).padStart(2, '0');
}

function parseLocalDate(value: string): Date | null {
  if (!value) return null;
  const [y, m, d] = value.split('-').map((item) => Number(item));
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d, 0, 0, 0, 0);
}

function formatLocalDate(date: Date): string {
  return `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
}

export default function DateOnlyPicker({ value, onChange, placeholder = '请选择日期' }: DateOnlyPickerProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const initialDate = parseLocalDate(value) ?? new Date();
  const [viewYear, setViewYear] = useState(initialDate.getFullYear());
  const [viewMonth, setViewMonth] = useState(initialDate.getMonth());
  const [selectedDay, setSelectedDay] = useState<Date>(initialDate);

  useEffect(() => {
    if (!open) return;
    const current = parseLocalDate(value) ?? new Date();
    setViewYear(current.getFullYear());
    setViewMonth(current.getMonth());
    setSelectedDay(current);
  }, [open, value]);

  useEffect(() => {
    if (!open) return;
    const onMouseDown = (event: MouseEvent) => {
      if (!rootRef.current) return;
      if (event.target instanceof Node && !rootRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', onMouseDown);
    return () => document.removeEventListener('mousedown', onMouseDown);
  }, [open]);

  const monthStart = new Date(viewYear, viewMonth, 1);
  const monthStartWeekday = monthStart.getDay();
  const daysInMonth = new Date(viewYear, viewMonth + 1, 0).getDate();
  const daysInPrevMonth = new Date(viewYear, viewMonth, 0).getDate();
  const dayCells: Array<{ date: Date; inMonth: boolean }> = [];
  for (let i = 0; i < 42; i += 1) {
    const dayNum = i - monthStartWeekday + 1;
    if (dayNum <= 0) {
      dayCells.push({ date: new Date(viewYear, viewMonth - 1, daysInPrevMonth + dayNum), inMonth: false });
    } else if (dayNum > daysInMonth) {
      dayCells.push({ date: new Date(viewYear, viewMonth + 1, dayNum - daysInMonth), inMonth: false });
    } else {
      dayCells.push({ date: new Date(viewYear, viewMonth, dayNum), inMonth: true });
    }
  }

  const monthNames = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
  const monthLabel = `${monthNames[viewMonth]}${viewYear}`;
  const weekLabels = ['S', 'M', 'T', 'W', 'T', 'F', 'S'];

  return (
    <div ref={rootRef} className="relative w-full">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className={`flex h-10 w-full items-center rounded-sm border bg-white px-3 text-left text-[14px] ${
          open ? 'border-[#ee4d2d]' : 'border-[#d9d9d9]'
        }`}
      >
        <Calendar size={14} className="text-[#a8a8a8]" />
        <span className={`ml-2 flex-1 ${value ? 'text-[#555]' : 'text-[#b0b0b0]'}`}>{value || placeholder}</span>
      </button>
      {open && (
        <div className="absolute left-0 top-[42px] z-40 w-[360px] overflow-hidden rounded-sm border border-[#d9d9d9] bg-white shadow-[0_8px_24px_rgba(0,0,0,0.12)]">
          <div className="p-3">
            <div className="mb-2 flex items-center justify-between">
              <button
                type="button"
                onClick={() => {
                  const prev = new Date(viewYear - 1, viewMonth, 1);
                  setViewYear(prev.getFullYear());
                  setViewMonth(prev.getMonth());
                }}
                className="rounded p-1 text-[#8a8a8a] hover:bg-[#f5f5f5]"
              >
                <ChevronLeft size={14} />
              </button>
              <button
                type="button"
                onClick={() => {
                  const prev = new Date(viewYear, viewMonth - 1, 1);
                  setViewYear(prev.getFullYear());
                  setViewMonth(prev.getMonth());
                }}
                className="rounded p-1 text-[#8a8a8a] hover:bg-[#f5f5f5]"
              >
                <ChevronLeft size={14} />
              </button>
              <div className="text-[16px] font-semibold text-[#333]">{monthLabel}</div>
              <button
                type="button"
                onClick={() => {
                  const next = new Date(viewYear, viewMonth + 1, 1);
                  setViewYear(next.getFullYear());
                  setViewMonth(next.getMonth());
                }}
                className="rounded p-1 text-[#8a8a8a] hover:bg-[#f5f5f5]"
              >
                <ChevronRight size={14} />
              </button>
              <button
                type="button"
                onClick={() => {
                  const next = new Date(viewYear + 1, viewMonth, 1);
                  setViewYear(next.getFullYear());
                  setViewMonth(next.getMonth());
                }}
                className="rounded p-1 text-[#8a8a8a] hover:bg-[#f5f5f5]"
              >
                <ChevronRight size={14} />
              </button>
            </div>
            <div className="grid grid-cols-7 text-center text-[13px] text-[#777]">
              {weekLabels.map((item) => (
                <div key={item} className="py-1">{item}</div>
              ))}
            </div>
            <div className="grid grid-cols-7 gap-y-1 text-center text-[14px]">
              {dayCells.map((item) => {
                const isSelected =
                  item.date.getFullYear() === selectedDay.getFullYear() &&
                  item.date.getMonth() === selectedDay.getMonth() &&
                  item.date.getDate() === selectedDay.getDate();
                return (
                  <button
                    key={`${item.date.toISOString()}-${item.inMonth ? 'm' : 'x'}`}
                    type="button"
                    onClick={() => setSelectedDay(item.date)}
                    className={`mx-auto h-8 w-8 rounded-full ${
                      isSelected ? 'bg-[#ee4d2d] text-white' : item.inMonth ? 'text-[#333] hover:bg-[#f5f5f5]' : 'text-[#c5c5c5]'
                    }`}
                  >
                    {item.date.getDate()}
                  </button>
                );
              })}
            </div>
          </div>
          <div className="border-t border-[#f0f0f0] px-3 py-2 text-right">
            <button
              type="button"
              onClick={() => {
                onChange(formatLocalDate(selectedDay));
                setOpen(false);
              }}
              className="h-8 rounded bg-[#ee4d2d] px-4 text-[13px] text-white hover:bg-[#d83f21]"
            >
              确认
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
