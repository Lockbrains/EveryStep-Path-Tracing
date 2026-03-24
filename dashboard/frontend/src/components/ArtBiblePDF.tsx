"use client";

import {
  Document,
  Page,
  Text,
  View,
  Image,
  StyleSheet,
} from "@react-pdf/renderer";
import type { BoardData, StepState, BenchmarkData } from "@/lib/types";

function RichText({ children, style }: { children: string; style?: object }) {
  const parts = children.split(/(\*\*[^*]+\*\*)/g);
  return (
    <Text style={style}>
      {parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**")) {
          return (
            <Text key={i} style={{ fontFamily: "Helvetica-Bold" }}>
              {part.slice(2, -2)}
            </Text>
          );
        }
        return <Text key={i}>{part}</Text>;
      })}
    </Text>
  );
}

const ACCENT = "#6366f1";
const BG = "#ffffff";
const FG = "#18181b";
const MUTED = "#71717a";
const BORDER = "#e4e4e7";

const s = StyleSheet.create({
  page: {
    fontFamily: "Helvetica",
    fontSize: 10,
    color: FG,
    backgroundColor: BG,
    paddingTop: 48,
    paddingBottom: 48,
    paddingHorizontal: 48,
  },
  header: {
    position: "absolute",
    top: 16,
    left: 48,
    right: 48,
    flexDirection: "row",
    justifyContent: "space-between",
    borderBottom: `0.5pt solid ${BORDER}`,
    paddingBottom: 6,
  },
  headerText: { fontSize: 7, color: MUTED },
  footer: {
    position: "absolute",
    bottom: 16,
    left: 48,
    right: 48,
    textAlign: "center",
    fontSize: 7,
    color: MUTED,
  },
  coverPage: {
    justifyContent: "center",
    alignItems: "center",
  },
  coverTitle: {
    fontSize: 36,
    fontWeight: 700,
    color: ACCENT,
    marginBottom: 8,
    textAlign: "center",
  },
  coverSubtitle: {
    fontSize: 14,
    color: MUTED,
    marginBottom: 24,
    textAlign: "center",
  },
  coverDate: {
    fontSize: 10,
    color: MUTED,
    textAlign: "center",
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: 700,
    color: FG,
    marginBottom: 4,
  },
  sectionNum: {
    fontSize: 12,
    fontWeight: 600,
    color: ACCENT,
    marginBottom: 2,
  },
  divider: {
    height: 2,
    backgroundColor: ACCENT,
    marginBottom: 16,
    borderRadius: 1,
  },
  imageGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginBottom: 12,
  },
  imageCell: {
    width: "48%",
    borderRadius: 6,
    overflow: "hidden",
    border: `0.5pt solid ${BORDER}`,
  },
  img: {
    width: "100%",
    objectFit: "contain",
  },
  annotation: {
    fontSize: 10,
    lineHeight: 1.6,
    color: FG,
    marginBottom: 12,
  },
  metaRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingTop: 8,
    borderTop: `0.5pt solid ${BORDER}`,
    marginTop: 4,
  },
  metaLabel: {
    fontSize: 8,
    color: MUTED,
  },
  metaValue: {
    fontSize: 8,
    fontWeight: 600,
    color: FG,
  },
  dimBadge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 8,
    fontSize: 7,
    marginRight: 4,
    marginBottom: 4,
  },
  dimRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    marginTop: 6,
  },
  tocEntry: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: 6,
    borderBottom: `0.5pt solid ${BORDER}`,
  },
  tocNum: {
    fontSize: 10,
    fontWeight: 600,
    color: ACCENT,
    width: 24,
  },
  tocTitle: {
    fontSize: 10,
    fontWeight: 600,
    color: FG,
    flex: 1,
  },
  tocScore: {
    fontSize: 9,
    color: MUTED,
    width: 50,
    textAlign: "right",
  },
});

function dimColor(score: number): string {
  if (score >= 0.7) return "#059669";
  if (score >= 0.4) return "#d97706";
  return "#dc2626";
}

function dimBg(score: number): string {
  if (score >= 0.7) return "#ecfdf5";
  if (score >= 0.4) return "#fffbeb";
  return "#fef2f2";
}

interface ArtBiblePDFProps {
  title: string;
  steps: StepState[];
  boards: BoardData[];
  benchmark?: BenchmarkData | null;
  imageMap?: Record<string, string>;
}

function CoverPage({ title }: { title: string }) {
  const date = new Date().toLocaleDateString("en-US", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  return (
    <Page size="A4" style={[s.page, s.coverPage]}>
      <Text style={s.coverTitle}>{title}</Text>
      <Text style={s.coverSubtitle}>Art Bible</Text>
      <Text style={s.coverDate}>{date}</Text>
      <Text style={[s.coverDate, { marginTop: 8, fontSize: 8 }]}>
        Generated with EveryStep Path Tracing
      </Text>
    </Page>
  );
}

function TOCPage({
  steps,
}: {
  steps: StepState[];
}) {
  const completed = steps.filter((st) => st.status === "complete");
  return (
    <Page size="A4" style={s.page}>
      <View style={s.header}>
        <Text style={s.headerText}>Art Bible</Text>
        <Text style={s.headerText}>Table of Contents</Text>
      </View>
      <Text style={[s.sectionTitle, { marginBottom: 16 }]}>Contents</Text>
      {completed.map((st) => (
        <View key={st.step} style={s.tocEntry}>
          <Text style={s.tocNum}>{String(st.step).padStart(2, "0")}</Text>
          <Text style={s.tocTitle}>{st.title}</Text>
          <Text style={s.tocScore}>
            {st.finalScore != null ? st.finalScore.toFixed(3) : "—"}
          </Text>
        </View>
      ))}
    </Page>
  );
}

function SectionPage({
  step,
  board,
  pageNum,
  imageMap,
}: {
  step: StepState;
  board: BoardData | undefined;
  pageNum: number;
  imageMap: Record<string, string>;
}) {
  const imgIds = board?.imageIds ?? step.boardImageIds;
  const annotation = board?.annotation ?? step.boardAnnotation;

  return (
    <Page size="A4" style={s.page} wrap>
      <View style={s.header} fixed>
        <Text style={s.headerText}>{step.title}</Text>
        <Text style={s.headerText}>Art Bible</Text>
      </View>
      <Text style={s.footer} fixed render={({ pageNumber }) => `${pageNumber}`} />

      <Text style={s.sectionNum}>
        {String(step.step).padStart(2, "0")}
      </Text>
      <Text style={s.sectionTitle}>{step.title}</Text>
      <View style={s.divider} />

      {imgIds.length > 0 && (
        <View style={s.imageGrid}>
          {imgIds.slice(0, 4).map((id) => {
            const src = imageMap[id];
            if (!src) return null;
            return (
              <View key={id} style={s.imageCell}>
                <Image src={src} style={s.img} />
              </View>
            );
          })}
        </View>
      )}

      {annotation && <RichText style={s.annotation}>{annotation}</RichText>}

      {step.finalDimensions.length > 0 && (
        <View style={s.dimRow}>
          {step.finalDimensions.map((d) => (
            <Text
              key={d.dimension}
              style={[
                s.dimBadge,
                { color: dimColor(d.score), backgroundColor: dimBg(d.score) },
              ]}
            >
              {d.dimension}: {d.score.toFixed(2)}
            </Text>
          ))}
        </View>
      )}

      <View style={s.metaRow}>
        <View>
          <Text style={s.metaLabel}>Quality Score</Text>
          <Text style={s.metaValue}>
            {step.finalScore?.toFixed(3) ?? "—"}
          </Text>
        </View>
        <View>
          <Text style={s.metaLabel}>Images</Text>
          <Text style={s.metaValue}>{imgIds.length}</Text>
        </View>
        <View>
          <Text style={s.metaLabel}>Attempts</Text>
          <Text style={s.metaValue}>{step.attempt + 1}</Text>
        </View>
      </View>
    </Page>
  );
}

export function ArtBiblePDF({
  title,
  steps,
  boards,
  benchmark,
  imageMap = {},
}: ArtBiblePDFProps) {
  const completedSteps = steps.filter((st) => st.status === "complete");

  return (
    <Document
      title={`${title} - Art Bible`}
      author="EveryStep Path Tracing"
    >
      <CoverPage title={title} />
      <TOCPage steps={steps} />
      {completedSteps.map((st, i) => (
        <SectionPage
          key={st.step}
          step={st}
          board={boards.find((b) => b.stepIndex === st.step - 1)}
          pageNum={i + 3}
          imageMap={imageMap}
        />
      ))}
    </Document>
  );
}
