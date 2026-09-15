"use client";

interface Props {
  src: string;
  label: string;
}

export function VideoPlayer({ src, label }: Props) {
  return (
    <div className="rounded-lg overflow-hidden bg-black">
      <div className="px-4 py-2 text-sm text-slate-300 bg-slate-800">{label}</div>
      <video src={src} controls className="w-full" />
    </div>
  );
}
