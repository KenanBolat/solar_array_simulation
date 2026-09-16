import { ImageResponse } from "next/og";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center",
          background: "#0b0d11", borderRadius: 7,
        }}
      >
        <div style={{ width: 14, height: 14, border: "3px solid #2dd4ee", borderRadius: 3 }} />
      </div>
    ),
    { ...size }
  );
}
