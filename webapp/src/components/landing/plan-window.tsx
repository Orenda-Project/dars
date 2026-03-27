// src/components/landing/plan-window.tsx

export function PlanWindow() {
  return (
    <div
      style={{
        width: "100%",
        maxWidth: 700,
        background: "#231c18",
        border: "1px solid #3a2e28",
        borderRadius: 10,
        overflow: "hidden",
        boxShadow: "0 40px 100px rgba(0,0,0,0.6)",
        transform: "translateY(-48px)",
      }}
    >
      {/* Window chrome */}
      <div
        style={{
          background: "#17110e",
          padding: "10px 16px",
          display: "flex",
          alignItems: "center",
          gap: 8,
          borderBottom: "1px solid #2e2420",
        }}
      >
        <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#bf4e30", opacity: 0.6 }} />
        <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#c47a3a", opacity: 0.6 }} />
        <div style={{ width: 10, height: 10, borderRadius: "50%", background: "#4a7c59", opacity: 0.6 }} />
        <div
          style={{
            flex: 1,
            background: "#2e2420",
            borderRadius: 4,
            padding: "4px 12px",
            fontSize: 11,
            color: "#5a4a42",
            fontFamily: "monospace",
            margin: "0 8px",
          }}
        >
          dars.taleemabad.com/dashboard
        </div>
      </div>

      {/* Window body */}
      <div style={{ display: "grid", gridTemplateColumns: "200px 1fr" }}>
        {/* Sidebar */}
        <div style={{ background: "#1a1410", borderRight: "1px solid #2e2420", padding: "20px 16px" }}>
          <div style={{ fontSize: 10, fontWeight: 700, letterSpacing: "1.5px", textTransform: "uppercase", color: "#4a3830", marginBottom: 12 }}>
            My Plans
          </div>
          {[
            { label: "The Water Cycle", active: true },
            { label: "Fractions — Grade 5", active: false },
            { label: "Urdu Comprehension", active: false },
            { label: "Forces & Motion", active: false },
            { label: "Poetry Analysis", active: false },
          ].map(({ label, active }) => (
            <div
              key={label}
              style={{
                padding: "7px 10px",
                borderRadius: 5,
                fontSize: 12,
                color: active ? "#e8a07a" : "#6a5a52",
                fontWeight: active ? 600 : 400,
                marginBottom: 2,
                background: active ? "rgba(191,78,48,0.15)" : "transparent",
              }}
            >
              {active ? "▸ " : ""}{label}
            </div>
          ))}
        </div>

        {/* Main */}
        <div style={{ padding: "24px 28px" }}>
          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 20, paddingBottom: 16, borderBottom: "1px solid #2e2420" }}>
            <div>
              <div style={{ fontFamily: "Georgia, serif", fontSize: 16, fontWeight: 700, color: "#faf7f2", marginBottom: 4 }}>
                The Water Cycle
              </div>
              <div style={{ fontSize: 11, color: "#6a5a52" }}>Grade 4 · Science · 45 min · Punjab Board</div>
            </div>
            <div style={{ fontSize: 10, fontWeight: 600, padding: "3px 9px", borderRadius: 20, background: "rgba(191,78,48,0.15)", color: "#e8a07a", whiteSpace: "nowrap" }}>
              AI Generated
            </div>
          </div>

          <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: "1.5px", textTransform: "uppercase", color: "#e8a07a", marginBottom: 8 }}>
            Learning Objectives
          </div>
          {[
            "Identify and describe the stages of the water cycle",
            "Explain evaporation and condensation using examples",
            "Describe how precipitation forms and its effects",
          ].map((obj) => (
            <div key={obj} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "#8a7a72", marginBottom: 5 }}>
              <div style={{ width: 5, height: 5, borderRadius: "50%", background: "#bf4e30", opacity: 0.6, flexShrink: 0 }} />
              {obj}
            </div>
          ))}

          <div style={{ fontSize: 9, fontWeight: 700, letterSpacing: "1.5px", textTransform: "uppercase", color: "#e8a07a", marginBottom: 8, marginTop: 16 }}>
            Activities
          </div>
          {[
            { num: "i.", text: "Warm-up discussion — \"Where does rain come from?\"", dur: "5 min" },
            { num: "ii.", text: "Diagram labelling exercise", dur: "10 min" },
            { num: "iii.", text: "Group experiment — evaporation in a bag", dur: "20 min" },
            { num: "iv.", text: "Exit ticket — 3 facts learned today", dur: "5 min" },
          ].map(({ num, text, dur }) => (
            <div key={num} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 10px", background: "#1a1410", borderRadius: 5, marginBottom: 4 }}>
              <span style={{ fontFamily: "Georgia, serif", fontSize: 12, color: "#bf4e30", fontStyle: "italic", minWidth: 20 }}>{num}</span>
              <span style={{ fontSize: 12, color: "#7a6a62" }}>{text}</span>
              <span style={{ fontSize: 10, color: "#4a3830", marginLeft: "auto" }}>{dur}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
