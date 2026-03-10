import { useState, useRef, useEffect } from 'react';
import { Download, ChevronDown } from 'lucide-react';

interface ExportButtonProps {
  data: Record<string, unknown>[] | Record<string, unknown>;
  filename: string;
  label?: string;
}

function flattenForCSV(
  data: Record<string, unknown>[] | Record<string, unknown>,
): Record<string, unknown>[] {
  if (Array.isArray(data)) return data;
  return [data];
}

function toCSV(data: Record<string, unknown>[]): string {
  if (data.length === 0) return '';

  const headers = Array.from(
    data.reduce<Set<string>>((keys, row) => {
      Object.keys(row).forEach((k) => keys.add(k));
      return keys;
    }, new Set()),
  );

  const escapeCell = (value: unknown): string => {
    const str = value === null || value === undefined ? '' : String(value);
    if (str.includes(',') || str.includes('"') || str.includes('\n')) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };

  const rows = data.map((row) =>
    headers.map((h) => escapeCell(row[h])).join(','),
  );

  return [headers.join(','), ...rows].join('\n');
}

function triggerDownload(content: string, filename: string, mimeType: string) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

export default function ExportButton({
  data,
  filename,
  label = 'Export',
}: ExportButtonProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      ) {
        setOpen(false);
      }
    }
    if (open) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  const handleExportCSV = () => {
    const rows = flattenForCSV(data);
    const csv = toCSV(rows);
    triggerDownload(csv, `${filename}.csv`, 'text/csv;charset=utf-8;');
    setOpen(false);
  };

  const handleExportJSON = () => {
    const json = JSON.stringify(data, null, 2);
    triggerDownload(json, `${filename}.json`, 'application/json');
    setOpen(false);
  };

  return (
    <div className="relative" ref={containerRef}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 rounded-lg border border-navy-700 bg-navy-800 px-3 py-1.5 text-xs font-medium text-navy-300 transition hover:bg-navy-700 hover:text-navy-200"
      >
        <Download className="h-3.5 w-3.5" />
        {label}
        <ChevronDown
          className={`h-3 w-3 transition-transform ${open ? 'rotate-180' : ''}`}
        />
      </button>
      {open && (
        <div className="absolute right-0 z-50 mt-1 w-40 overflow-hidden rounded-lg border border-navy-700 bg-navy-900 shadow-xl">
          <button
            onClick={handleExportCSV}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-navy-300 transition hover:bg-navy-800 hover:text-navy-200"
          >
            Export CSV
          </button>
          <button
            onClick={handleExportJSON}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-navy-300 transition hover:bg-navy-800 hover:text-navy-200"
          >
            Export JSON
          </button>
        </div>
      )}
    </div>
  );
}
