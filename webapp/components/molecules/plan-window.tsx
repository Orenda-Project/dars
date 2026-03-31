export function PlanWindow() {
  return (
    <div
      className="w-full max-w-[700px] rounded-[10px] overflow-hidden -translate-y-12 sm:-translate-y-6"
      style={{
        background: "#231c18",
        border: "1px solid #3a2e28",
        boxShadow: "0 40px 100px rgba(0,0,0,0.6)",
      }}
    >
      {/* Window chrome */}
      <div
        className="flex items-center gap-2 px-4 py-2.5 border-b"
        style={{ background: "#17110e", borderColor: "#2e2420" }}
      >
        <div className="w-2.5 h-2.5 rounded-full bg-dars-terra opacity-60" />
        <div className="w-2.5 h-2.5 rounded-full opacity-60" style={{ background: "#c47a3a" }} />
        <div className="w-2.5 h-2.5 rounded-full opacity-60" style={{ background: "#4a7c59" }} />
        <div
          className="flex-1 rounded px-3 py-1 text-[11px] font-mono mx-2 hidden sm:block"
          style={{ background: "#2e2420", color: "#5a4a42" }}
        >
          dars.taleemabad.com/dashboard
        </div>
      </div>

      {/* Window body */}
      <div className="grid grid-cols-1 sm:grid-cols-[200px_1fr]">
        {/* Sidebar — hidden on mobile */}
        <div
          className="border-r p-5 hidden sm:block"
          style={{ background: "#1a1410", borderColor: "#2e2420" }}
        >
          <div className="text-[10px] font-bold tracking-[1.5px] uppercase mb-3" style={{ color: "#4a3830" }}>
            My Plans
          </div>
          {[
            { label: "The Water Cycle", active: true },
            { label: "Fractions — Grade 5", active: false },
            { label: "Urdu Reading — KG", active: false },
            { label: "Forces & Motion", active: false },
            { label: "Poetry — Class 7", active: false },
          ].map(({ label, active }) => (
            <div
              key={label}
              className="px-2.5 py-[7px] rounded-md text-[12px] mb-0.5"
              style={{
                color: active ? "#e8a07a" : "#6a5a52",
                fontWeight: active ? 600 : 400,
                background: active ? "rgba(191,78,48,0.15)" : "transparent",
              }}
            >
              {active ? "▸ " : ""}{label}
            </div>
          ))}
        </div>

        {/* Main content */}
        <div className="p-6 sm:p-4">
          <div
            className="flex items-start justify-between mb-5 pb-4 border-b"
            style={{ borderColor: "#2e2420" }}
          >
            <div>
              <div className="font-serif text-base font-bold mb-1" style={{ color: "#faf7f2" }}>
                The Water Cycle
              </div>
              <div className="text-[11px]" style={{ color: "#6a5a52" }}>
                Grade 4 · Science · 45 min · Punjab Board
              </div>
            </div>
            <div
              className="text-[10px] font-semibold px-2 py-[3px] rounded-full whitespace-nowrap"
              style={{ background: "rgba(191,78,48,0.15)", color: "#e8a07a" }}
            >
              Ready
            </div>
          </div>

          <div className="text-[9px] font-bold tracking-[1.5px] uppercase mb-2" style={{ color: "#e8a07a" }}>
            Learning Objectives
          </div>
          {[
            "Identify and explain the three stages of the water cycle",
            "Connect evaporation and condensation to daily weather",
            "Describe how precipitation forms and reaches the ground",
          ].map((obj) => (
            <div key={obj} className="flex items-center gap-2 text-[12px] mb-1.5" style={{ color: "#8a7a72" }}>
              <div className="w-[5px] h-[5px] rounded-full flex-shrink-0 bg-dars-terra opacity-60" />
              {obj}
            </div>
          ))}

          <div className="text-[9px] font-bold tracking-[1.5px] uppercase mb-2 mt-4" style={{ color: "#e8a07a" }}>
            Activities
          </div>
          {[
            { num: "i.", text: "Opening — Where does rain come from?", dur: "5 min" },
            { num: "ii.", text: "Diagram labelling — complete the water cycle", dur: "10 min" },
            { num: "iii.", text: "Experiment — evaporation in a sealed bag", dur: "20 min" },
            { num: "iv.", text: "Exit ticket — three things I learned today", dur: "5 min" },
          ].map(({ num, text, dur }) => (
            <div
              key={num}
              className="flex items-center gap-2.5 px-2.5 py-2 rounded-md mb-1"
              style={{ background: "#1a1410" }}
            >
              <span className="font-serif text-[12px] italic min-w-[20px]" style={{ color: "#bf4e30" }}>{num}</span>
              <span className="text-[12px] truncate" style={{ color: "#7a6a62" }}>{text}</span>
              <span className="text-[10px] ml-auto flex-shrink-0" style={{ color: "#4a3830" }}>{dur}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
