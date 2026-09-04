import { useEffect, useState } from "react";
import { artifactFileUrl, getChunk } from "../../lib/api";

/** Resolves a chunk's linked artifact (Phase 4's `chunk.artifact_id`) to a
 * displayable image, since evidence items only carry `chunk_id` — not
 * `artifact_id` directly. Never fabricates an image: renders nothing until
 * a real artifact is confirmed. */
export function ArtifactImage({ chunkId, alt }: { chunkId: string; alt: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setSrc(null);
    setFailed(false);
    getChunk(chunkId)
      .then((chunk) => {
        if (cancelled) return;
        if (chunk.artifact_id) {
          setSrc(artifactFileUrl(chunk.artifact_id));
        } else {
          setFailed(true);
        }
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [chunkId]);

  if (failed) return null;
  if (!src) {
    return (
      <div className="h-32 w-full animate-pulse rounded-lg border border-border bg-surface" />
    );
  }
  return (
    <img
      src={src}
      alt={alt}
      className="max-h-64 w-auto rounded-lg border border-border object-contain"
      onError={() => setFailed(true)}
    />
  );
}
