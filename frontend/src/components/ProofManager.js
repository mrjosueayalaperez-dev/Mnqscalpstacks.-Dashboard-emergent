import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { BadgeCheck, Trash2, Upload } from "lucide-react";

const BACKEND = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND}/api`;

/** Admin uploader for the "Verified Results" proof gallery. */
export default function ProofManager() {
  const [shots, setShots] = useState([]);
  const [caption, setCaption] = useState("");
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef(null);

  const refresh = useCallback(() => {
    axios.get(`${API}/proof/list`)
      .then((r) => setShots(r.data.shots || []))
      .catch((e) => console.error("Proof list error:", e));
  }, []);

  useEffect(() => { refresh(); }, [refresh]);

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) { toast.error("Pick an image first"); return; }
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("caption", caption);
      await axios.post(`${API}/proof/upload`, form);
      toast.success("Proof shot published");
      setCaption("");
      fileRef.current.value = "";
      refresh();
    } catch (e) {
      toast.error("Upload failed: " + (e.response?.data?.detail || e.message));
    }
    setUploading(false);
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Remove this proof shot from the site?")) return;
    try {
      await axios.delete(`${API}/proof/${id}`);
      toast.success("Removed");
      refresh();
    } catch (e) {
      toast.error("Delete failed");
    }
  };

  return (
    <div className="bg-[#121212] border border-white/10 rounded-sm p-4" data-testid="proof-manager">
      <h3 className="flex items-center gap-2 text-sm font-black text-white mb-3">
        <BadgeCheck className="w-4 h-4 text-[#34C759]" />
        PROOF GALLERY ({shots.length})
      </h3>

      {/* Upload form */}
      <div className="flex flex-col sm:flex-row gap-2 mb-4">
        <input
          type="file"
          ref={fileRef}
          accept="image/png,image/jpeg,image/webp,image/gif"
          className="flex-1 text-xs text-zinc-400 file:mr-2 file:px-3 file:py-1.5 file:bg-white/10 file:border-0 file:rounded-sm file:text-white file:text-xs file:cursor-pointer"
          data-testid="proof-file-input"
        />
        <input
          type="text"
          placeholder="Caption (e.g. July session receipts)"
          value={caption}
          onChange={(e) => setCaption(e.target.value)}
          className="flex-1 text-xs"
          data-testid="proof-caption-input"
        />
        <button
          onClick={handleUpload}
          disabled={uploading}
          className="flex items-center justify-center gap-1.5 px-4 py-2 bg-[#34C759] text-black text-xs font-black rounded-sm hover:bg-[#2DB84E] transition-colors disabled:opacity-50"
          data-testid="proof-upload-btn"
        >
          <Upload className="w-3.5 h-3.5" />
          {uploading ? "Publishing…" : "Publish"}
        </button>
      </div>

      {/* Existing shots */}
      {shots.length === 0 ? (
        <p className="text-xs text-zinc-600">No proof shots yet — upload your first receipt above.</p>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {shots.map((s) => (
            <div key={s.id} className="relative group border border-white/10 rounded-sm overflow-hidden" data-testid={`proof-admin-${s.id}`}>
              <img src={`${BACKEND}${s.url}`} alt={s.caption} className="w-full h-28 object-cover object-top" loading="lazy" />
              <div className="px-2 py-1 text-[0.55rem] text-zinc-500 font-mono truncate">{s.caption || "—"}</div>
              <button
                onClick={() => handleDelete(s.id)}
                className="absolute top-1 right-1 p-1 bg-black/70 rounded-sm opacity-0 group-hover:opacity-100 transition-opacity hover:bg-[#FF3B30]"
                data-testid={`proof-delete-${s.id}`}
              >
                <Trash2 className="w-3 h-3 text-white" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
