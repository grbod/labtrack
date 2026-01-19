import { useState, useCallback } from "react"
import Cropper from "react-easy-crop"
import type { Area, Point } from "react-easy-crop"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog"
import { ZoomIn, ZoomOut, RotateCcw, Loader2 } from "lucide-react"

interface ImageCropperProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  imageSrc: string
  onCropComplete: (croppedImageBlob: Blob) => void | Promise<void>
  aspectRatio?: number
  title?: string
}

// Helper to create a cropped image from canvas
async function getCroppedImg(
  imageSrc: string,
  pixelCrop: Area
): Promise<Blob> {
  const image = await createImage(imageSrc)
  const canvas = document.createElement("canvas")
  const ctx = canvas.getContext("2d")

  if (!ctx) {
    throw new Error("No 2d context")
  }

  // Set canvas size to the cropped area
  canvas.width = pixelCrop.width
  canvas.height = pixelCrop.height

  // Draw the cropped image
  ctx.drawImage(
    image,
    pixelCrop.x,
    pixelCrop.y,
    pixelCrop.width,
    pixelCrop.height,
    0,
    0,
    pixelCrop.width,
    pixelCrop.height
  )

  // Convert canvas to blob
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) {
          resolve(blob)
        } else {
          reject(new Error("Canvas is empty"))
        }
      },
      "image/png",
      1
    )
  })
}

function createImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.addEventListener("load", () => resolve(image))
    image.addEventListener("error", (error) => reject(error))
    image.src = url
  })
}

const ASPECT_PRESETS = [
  { label: "4:1", value: 4 },
  { label: "3:1", value: 3 },
  { label: "2:1", value: 2 },
  { label: "16:9", value: 16 / 9 },
  { label: "4:3", value: 4 / 3 },
  { label: "1:1", value: 1 },
]

export function ImageCropper({
  open,
  onOpenChange,
  imageSrc,
  onCropComplete,
  aspectRatio: initialAspectRatio,
  title = "Crop Image",
}: ImageCropperProps) {
  const [crop, setCrop] = useState<Point>({ x: 0, y: 0 })
  const [zoom, setZoom] = useState(1)
  const [croppedAreaPixels, setCroppedAreaPixels] = useState<Area | null>(null)
  const [aspectRatio, setAspectRatio] = useState<number>(initialAspectRatio || 4)
  const [isSaving, setIsSaving] = useState(false)
  const [mediaSize, setMediaSize] = useState<{ width: number; height: number } | null>(null)

  const onCropChange = useCallback((location: Point) => {
    setCrop(location)
  }, [])

  const onZoomChange = useCallback((newZoom: number) => {
    setZoom(newZoom)
  }, [])

  const onCropAreaComplete = useCallback(
    (_croppedArea: Area, croppedAreaPixels: Area) => {
      setCroppedAreaPixels(croppedAreaPixels)
    },
    []
  )

  // Handle media loaded to get initial dimensions
  const onMediaLoaded = useCallback((mediaSize: { width: number; height: number; naturalWidth: number; naturalHeight: number }) => {
    setMediaSize({ width: mediaSize.naturalWidth, height: mediaSize.naturalHeight })
  }, [])

  const handleSave = useCallback(async () => {
    // Use croppedAreaPixels if available, otherwise calculate from media size
    let cropArea = croppedAreaPixels
    if (!cropArea && mediaSize) {
      // Calculate a default crop area based on the aspect ratio and media size
      const mediaAspect = mediaSize.width / mediaSize.height
      let cropWidth = mediaSize.width
      let cropHeight = mediaSize.height

      if (mediaAspect > aspectRatio) {
        // Media is wider than desired aspect ratio
        cropWidth = mediaSize.height * aspectRatio
      } else {
        // Media is taller than desired aspect ratio
        cropHeight = mediaSize.width / aspectRatio
      }

      cropArea = {
        x: (mediaSize.width - cropWidth) / 2,
        y: (mediaSize.height - cropHeight) / 2,
        width: cropWidth,
        height: cropHeight,
      }
    }

    if (!cropArea) {
      console.error("No crop area available")
      return
    }

    setIsSaving(true)
    try {
      const croppedImage = await getCroppedImg(imageSrc, cropArea)
      await onCropComplete(croppedImage)
      onOpenChange(false)
    } catch (e) {
      console.error("Error cropping image:", e)
      // Don't close dialog on error - user can retry or cancel
    } finally {
      setIsSaving(false)
    }
  }, [croppedAreaPixels, mediaSize, aspectRatio, imageSrc, onCropComplete, onOpenChange])

  const handleReset = useCallback(() => {
    setCrop({ x: 0, y: 0 })
    setZoom(1)
    setAspectRatio(initialAspectRatio || 4)
  }, [initialAspectRatio])

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[500px]">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
        </DialogHeader>

        <div className="relative h-[300px] bg-slate-100 rounded-lg overflow-hidden">
          <Cropper
            image={imageSrc}
            crop={crop}
            zoom={zoom}
            aspect={aspectRatio}
            onCropChange={onCropChange}
            onZoomChange={onZoomChange}
            onCropComplete={onCropAreaComplete}
            onMediaLoaded={onMediaLoaded}
            showGrid={true}
            restrictPosition={false}
            style={{
              containerStyle: {
                borderRadius: "8px",
              },
            }}
          />
        </div>

        {/* Aspect ratio presets */}
        <div className="flex items-center gap-2 px-2">
          <span className="text-[12px] text-slate-500 mr-1">Ratio:</span>
          {ASPECT_PRESETS.map((preset) => (
            <button
              key={preset.label}
              onClick={() => setAspectRatio(preset.value)}
              className={`px-2 py-1 text-[11px] rounded transition-colors ${
                aspectRatio === preset.value
                  ? "bg-slate-900 text-white"
                  : "bg-slate-100 text-slate-600 hover:bg-slate-200"
              }`}
            >
              {preset.label}
            </button>
          ))}
        </div>

        {/* Zoom controls */}
        <div className="flex items-center gap-3 px-2">
          <ZoomOut className="h-4 w-4 text-slate-400" />
          <input
            type="range"
            value={zoom}
            min={1}
            max={3}
            step={0.1}
            onChange={(e) => setZoom(parseFloat(e.target.value))}
            className="flex-1 h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-slate-900"
          />
          <ZoomIn className="h-4 w-4 text-slate-400" />
          <Button
            variant="ghost"
            size="icon-sm"
            onClick={handleReset}
            title="Reset"
          >
            <RotateCcw className="h-4 w-4" />
          </Button>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={isSaving}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={isSaving}>
            {isSaving ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Saving...
              </>
            ) : (
              "Save"
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
