"use client";

import { useCallback, useRef } from "react";
import { ImagePlus, X } from "lucide-react";
import { imageUrl, uploadImage, deleteImage } from "@/lib/api";
import type { UploadedImage } from "@/lib/api";

export function ImageUpload({
  images,
  onChange,
  disabled,
}: {
  images: UploadedImage[];
  onChange: (imgs: UploadedImage[]) => void;
  disabled?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    async (files: FileList | null) => {
      if (!files || disabled) return;
      const newImages: UploadedImage[] = [];
      for (const file of Array.from(files)) {
        if (!file.type.startsWith("image/")) continue;
        try {
          const uploaded = await uploadImage(file);
          newImages.push(uploaded);
        } catch (e) {
          console.error("Upload failed:", e);
        }
      }
      if (newImages.length) onChange([...images, ...newImages]);
    },
    [images, onChange, disabled],
  );

  const handleRemove = useCallback(
    async (id: string) => {
      await deleteImage(id);
      onChange(images.filter((img) => img.id !== id));
    },
    [images, onChange],
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles],
  );

  return (
    <div>
      <label className="mb-1.5 block text-xs font-medium uppercase tracking-wide text-zinc-500">
        Reference Images (backward path)
      </label>

      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        className="flex min-h-[80px] flex-wrap items-center gap-2 rounded-lg border border-dashed border-zinc-700 bg-zinc-950/50 p-3"
      >
        {images.map((img) => (
          <div key={img.id} className="group relative">
            <img
              src={imageUrl(img.id)}
              alt={img.filename}
              className="h-16 w-16 rounded-md border border-zinc-700 object-cover"
            />
            {!disabled && (
              <button
                type="button"
                onClick={() => handleRemove(img.id)}
                className="absolute -right-1 -top-1 hidden rounded-full bg-red-600 p-0.5 text-white group-hover:block"
              >
                <X className="size-3" />
              </button>
            )}
            <p className="mt-0.5 max-w-[64px] truncate text-center text-[8px] text-zinc-600">
              {img.filename}
            </p>
          </div>
        ))}

        {!disabled && (
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            className="flex h-16 w-16 flex-col items-center justify-center rounded-md border border-dashed border-zinc-600 text-zinc-500 transition-colors hover:border-indigo-500 hover:text-indigo-400"
          >
            <ImagePlus className="size-5" />
            <span className="text-[8px]">Add</span>
          </button>
        )}

        {images.length === 0 && !disabled && (
          <span className="text-xs text-zinc-600">
            Drop images here or click + to upload
          </span>
        )}
      </div>

      <input
        ref={inputRef}
        type="file"
        accept="image/*"
        multiple
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
    </div>
  );
}
