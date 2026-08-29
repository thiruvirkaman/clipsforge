import { useEffect, useState } from 'react';
import api from '@/services/api';

/**
 * Fetches a media resource through the authenticated API client (so the
 * bearer token is attached) and exposes it as a blob object URL. There is
 * no public/static media mount -- `<img>`/`<video src>` can't send an
 * Authorization header directly, so this is how the frontend renders
 * clip thumbnails/video while still going through ownership-checked routes.
 */
export function useAuthenticatedMediaUrl(path: string | null | undefined): string | null {
  const [url, setUrl] = useState<string | null>(null);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;

    if (!path) {
      setUrl(null);
      return undefined;
    }

    api
      .get(path, { responseType: 'blob' })
      .then((res) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(res.data);
        setUrl(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setUrl(null);
      });

    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [path]);

  return url;
}
