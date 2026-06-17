"use client";

// image cropper component

import { useEffect, useRef, useState } from "react";
import type React from "react";
import { useTranslation } from "@/lib/i18n/useTranslation";

type ImageCropperProps = {
  file: File;
  onCrop: (croppedFile: File) => void;
  onCancel: () => void;
};

/**
 * crop selected image
 */
export function ImageCropperModal({ file, onCrop, onCancel }: ImageCropperProps) {
  const { t } = useTranslation();
  const [imageUrl, setImageUrl] = useState<string>("");
  const [scale, setScale] = useState<number>(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dimensions, setDimensions] = useState<{ width: number; height: number } | null>(null);
  const startDrag = useRef({ x: 0, y: 0 });
  const currentDragOffset = useRef({ x: 0, y: 0 });
  const containerRef = useRef<HTMLDivElement>(null);
  const imageRef = useRef<HTMLImageElement>(null);
  const viewportRef = useRef<HTMLDivElement>(null);

  // track touch pointers for pinch zoom
  const activePointers = useRef<{ [pointerId: number]: { x: number; y: number } }>({});
  const startPinchDistance = useRef<number>(0);
  const startPinchScale = useRef<number>(1);

  useEffect(() => {
    const url = URL.createObjectURL(file);
    setImageUrl(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);

  /**
   * constrain offset to bounds
   */
  function constrainOffset(x: number, y: number, currentScale: number, dims: { width: number; height: number } | null) {
    if (!dims) return { x, y };

    let baseWidth = 280;
    let baseHeight = 280;
    if (dims.width > dims.height) {
      baseHeight = 280;
      baseWidth = 280 * (dims.width / dims.height);
    } else {
      baseWidth = 280;
      baseHeight = 280 * (dims.height / dims.width);
    }

    const w = baseWidth * currentScale;
    const h = baseHeight * currentScale;

    const minX = 140 - w / 2;
    const maxX = w / 2 - 140;
    const minY = 140 - h / 2;
    const maxY = h / 2 - 140;

    const constrainedX = minX <= maxX ? Math.max(minX, Math.min(maxX, x)) : 0;
    const constrainedY = minY <= maxY ? Math.max(minY, Math.min(maxY, y)) : 0;

    return { x: constrainedX, y: constrainedY };
  }

  /**
   * handle drag start
   */
  function handlePointerDown(e: React.PointerEvent) {
    e.preventDefault();
    activePointers.current[e.pointerId] = { x: e.clientX, y: e.clientY };

    const pointerIds = Object.keys(activePointers.current);
    if (pointerIds.length === 2) {
      setIsDragging(false);
      const p1 = activePointers.current[Number(pointerIds[0])];
      const p2 = activePointers.current[Number(pointerIds[1])];
      const dx = p1.x - p2.x;
      const dy = p1.y - p2.y;
      startPinchDistance.current = Math.sqrt(dx * dx + dy * dy);
      startPinchScale.current = scale;
    } else if (pointerIds.length === 1) {
      setIsDragging(true);
      startDrag.current = { x: e.clientX, y: e.clientY };
      currentDragOffset.current = { ...offset };
    }

    if (containerRef.current) {
      containerRef.current.setPointerCapture(e.pointerId);
    }
  }

  /**
   * handle dragging
   */
  function handlePointerMove(e: React.PointerEvent) {
    if (e.pointerId in activePointers.current) {
      activePointers.current[e.pointerId] = { x: e.clientX, y: e.clientY };
    }

    const pointerIds = Object.keys(activePointers.current);
    if (pointerIds.length === 2) {
      const p1 = activePointers.current[Number(pointerIds[0])];
      const p2 = activePointers.current[Number(pointerIds[1])];
      const dx = p1.x - p2.x;
      const dy = p1.y - p2.y;
      const currentDistance = Math.sqrt(dx * dx + dy * dy);

      if (startPinchDistance.current > 0) {
        const factor = currentDistance / startPinchDistance.current;
        const newScale = Math.max(1, Math.min(3, startPinchScale.current * factor));
        setScale(newScale);
        setOffset((prev) => constrainOffset(prev.x, prev.y, newScale, dimensions));
      }
    } else if (isDragging && pointerIds.length === 1) {
      const dx = e.clientX - startDrag.current.x;
      const dy = e.clientY - startDrag.current.y;
      const nextOffset = {
        x: currentDragOffset.current.x + dx,
        y: currentDragOffset.current.y + dy,
      };
      setOffset(constrainOffset(nextOffset.x, nextOffset.y, scale, dimensions));
    }
  }

  /**
   * handle drag end
   */
  function handlePointerUp(e: React.PointerEvent) {
    delete activePointers.current[e.pointerId];
    if (containerRef.current) {
      try {
        containerRef.current.releasePointerCapture(e.pointerId);
      } catch (err) {
        // ignore capture errors
      }
    }

    const pointerIds = Object.keys(activePointers.current);
    if (pointerIds.length < 2) {
      startPinchDistance.current = 0;
    }

    if (pointerIds.length === 1) {
      const remainingId = Number(pointerIds[0]);
      const p = activePointers.current[remainingId];
      startDrag.current = { x: p.x, y: p.y };
      currentDragOffset.current = { ...offset };
      setIsDragging(true);
    } else {
      setIsDragging(false);
    }
  }

  /**
   * handle zoom scale change
   */
  function handleScaleChange(newScale: number) {
    setScale(newScale);
    setOffset((prev) => constrainOffset(prev.x, prev.y, newScale, dimensions));
  }

  /**
   * crop and apply
   */
  async function handleApply() {
    const img = imageRef.current;
    const viewport = viewportRef.current;
    if (!img || !viewport) return;

    const canvas = document.createElement("canvas");
    const cropSize = 400;
    canvas.width = cropSize;
    canvas.height = cropSize;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rect = img.getBoundingClientRect();
    const viewportRect = viewport.getBoundingClientRect();
    const naturalWidth = img.naturalWidth;
    const naturalHeight = img.naturalHeight;

    const scaleX = naturalWidth / rect.width;
    const scaleY = naturalHeight / rect.height;

    const sourceX = (viewportRect.left - rect.left) * scaleX;
    const sourceY = (viewportRect.top - rect.top) * scaleY;
    const sourceWidth = viewportRect.width * scaleX;
    const sourceHeight = viewportRect.height * scaleY;

    ctx.drawImage(
      img,
      sourceX,
      sourceY,
      sourceWidth,
      sourceHeight,
      0,
      0,
      cropSize,
      cropSize
    );

    canvas.toBlob((blob) => {
      if (blob) {
        const croppedFile = new File([blob], file.name, { type: "image/jpeg" });
        onCrop(croppedFile);
      }
    }, "image/jpeg", 0.82);
  }

  if (!imageUrl) return null;

  return (
    <div
      className="fixed inset-0 z-[300] flex flex-col bg-black/90 select-none"
      onClick={(e) => e.stopPropagation()}
    >
      <header className="flex h-14 items-center justify-center border-b border-white/10 px-4 bg-black z-10">
        <h2 className="text-base font-bold text-white">{t("editPhoto") ?? "Edit photo"}</h2>
      </header>

      <div
        ref={containerRef}
        className="relative flex-1 overflow-hidden touch-none"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
      >
        <img
          ref={imageRef}
          src={imageUrl}
          alt="crop preview"
          draggable={false}
          className="absolute max-w-none origin-center"
          onLoad={(e) => {
            const img = e.currentTarget;
            setDimensions({ width: img.naturalWidth, height: img.naturalHeight });
          }}
          style={{
            transform: `translate(calc(-50% + ${offset.x}px), calc(-50% + ${offset.y}px)) scale(${scale})`,
            top: "50%",
            left: "50%",
            width: dimensions
              ? dimensions.width > dimensions.height
                ? `${280 * (dimensions.width / dimensions.height)}px`
                : "280px"
              : "280px",
            height: dimensions
              ? dimensions.width > dimensions.height
                ? "280px"
                : `${280 * (dimensions.height / dimensions.width)}px`
              : "auto",
          }}
        />

        {/* crop frame overlay */}
        <div className="absolute inset-0 pointer-events-none flex flex-col">
          <div className="flex-1 bg-black/85" />
          <div className="flex h-[280px]">
            <div className="flex-1 bg-black/85" />
            <div
              ref={viewportRef}
              className="relative w-[280px] h-[280px] border-2 border-dashed border-white shadow-[0_0_0_9999px_rgba(0,0,0,0.85)]"
            >
              {/* grid lines */}
              <div className="absolute inset-0 grid grid-cols-3 grid-rows-3 opacity-40">
                <div className="border-r border-b border-white" />
                <div className="border-r border-b border-white" />
                <div className="border-b border-white" />
                <div className="border-r border-b border-white" />
                <div className="border-r border-b border-white" />
                <div className="border-b border-white" />
                <div className="border-r border-white" />
                <div className="border-r border-white" />
                <div />
              </div>
            </div>
            <div className="flex-1 bg-black/85" />
          </div>
          <div className="flex-1 bg-black/85" />
        </div>
      </div>

      <div className="flex flex-col gap-4 bg-black px-6 pb-8 pt-4 z-10">
        {/* zoom slider */}
        <div className="flex items-center gap-3">
          <span className="text-xs font-semibold text-white/50">−</span>
          <input
            type="range"
            min="1"
            max="3"
            step="0.02"
            value={scale}
            onChange={(e) => handleScaleChange(parseFloat(e.target.value))}
            className="flex-1 accent-primary h-1 bg-white/20 rounded-lg appearance-none cursor-pointer"
          />
          <span className="text-xs font-semibold text-white/50">+</span>
        </div>

        <div className="flex gap-3 mt-1">
          <button
            type="button"
            className="flex-1 rounded-xl bg-white/10 hover:bg-white/15 text-white h-11 text-sm font-semibold transition-colors"
            onClick={onCancel}
          >
            {t("cancelButton") ?? "Cancel"}
          </button>
          <button
            type="button"
            className="flex-1 rounded-xl bg-primary hover:bg-primary/95 text-white h-11 text-sm font-semibold transition-all"
            onClick={handleApply}
          >
            {t("apply") ?? "Apply"}
          </button>
        </div>
      </div>
    </div>
  );
}
