/**
 * directUpload.ts — Sube archivos directo a S3 vía presigned POST (generate_presigned_post).
 *
 * Bypassea el límite de 6MB de payload de Lambda Function URL. NO usa PUT simple —
 * el backend firma un POST multipart/form-data con content-length-range real (ver
 * api/routers/uploads.py). El progreso se trackea con XMLHttpRequest (fetch no expone
 * upload.onprogress).
 */
"use client";

const API_URL = "/api-proxy";

function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem("taxops_token");
}

type PresignedUpload = {
  filename: string;
  s3_key: string;
  url: string;
  fields: Record<string, string>;
};

type PresignResponse = {
  uploads: PresignedUpload[];
  rechazados: { filename: string; motivo: string }[];
};

export type UploadResult = {
  filename: string;
  s3_key: string;
  error?: string;
};

function uploadOne(file: File, presigned: PresignedUpload, onProgress?: (pct: number) => void): Promise<UploadResult> {
  return new Promise((resolve) => {
    const fd = new FormData();
    Object.entries(presigned.fields).forEach(([k, v]) => fd.append(k, v));
    fd.append("file", file);

    const xhr = new XMLHttpRequest();
    xhr.open("POST", presigned.url);

    if (onProgress) {
      xhr.upload.onprogress = (e) => {
        if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
      };
    }

    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve({ filename: presigned.filename, s3_key: presigned.s3_key });
      } else {
        resolve({ filename: presigned.filename, s3_key: presigned.s3_key, error: `Error subiendo (HTTP ${xhr.status})` });
      }
    };
    xhr.onerror = () => {
      resolve({ filename: presigned.filename, s3_key: presigned.s3_key, error: "Error de red subiendo el archivo" });
    };

    xhr.send(fd);
  });
}

export async function uploadFiles(
  files: File[],
  contexto: "facturas" | "exogenas",
  onProgress?: (pct: number) => void
): Promise<UploadResult[]> {
  const token = getToken();
  const presignRes = await fetch(`${API_URL}/uploads/presign`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      contexto,
      archivos: files.map((f) => ({ filename: f.name, content_type: f.type || "application/octet-stream" })),
    }),
  });

  if (!presignRes.ok) {
    const err = await presignRes.json().catch(() => ({ detail: "Error al generar URLs de subida" }));
    throw new Error(err.detail || "Error al generar URLs de subida");
  }

  const body: PresignResponse = await presignRes.json();
  const byName = new Map(files.map((f) => [f.name, f]));

  const rejected: UploadResult[] = body.rechazados.map((r) => ({
    filename: r.filename,
    s3_key: "",
    error: r.motivo,
  }));

  const total = body.uploads.length;
  let completed = 0;
  const results = await Promise.all(
    body.uploads.map(async (presigned) => {
      const file = byName.get(presigned.filename);
      if (!file) return { filename: presigned.filename, s3_key: presigned.s3_key, error: "Archivo no encontrado" };
      const result = await uploadOne(file, presigned, () => {
        // progreso agregado simple: cuenta archivos completos, no bytes exactos entre N uploads paralelos
      });
      completed += 1;
      if (onProgress) onProgress(Math.round((completed / total) * 100));
      return result;
    })
  );

  return [...results, ...rejected];
}
