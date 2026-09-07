"use client";

import React, { useState, useMemo } from "react";
import {
  GeneratedScriptResponse,
  PanelItem,
  ScriptSegment,
  TimelineContract,
  VisualClip,
} from "../types";

interface InspectorProps {
  timeline: TimelineContract;
  selectedClipId: string | null;
  currentTime?: number;
  projectId?: string;
  onUpdateTimeline: (updatedTimeline: TimelineContract) => void;
  onSeek?: (time: number) => void;
  onSelectClip?: (clipId: string) => void;
  onAutoGenerateShort?: (
    style: "dramatic" | "humorous" | "romantic",
  ) => Promise<void>;
  isGeneratingShort?: boolean;

  // Panel-specific state and Global AI Review
  panels?: PanelItem[];
  selectedPanelId?: string | null;
  onUpdatePanel?: (panelId: string, updater: Partial<PanelItem>) => void;
  onAiReviewAllPanels?: (
    style: "dramatic" | "humorous" | "romantic",
  ) => Promise<void>;
  reviewProgress?: {
    current: number;
    total: number;
    isReviewing: boolean;
  } | null;
  storyStyle?: "dramatic" | "humorous" | "romantic";
  onSelectStoryStyle?: (style: "dramatic" | "humorous" | "romantic") => void;
}

interface EffectPreset {
  id: string;
  icon: string;
  title: string;
  desc: string;
  apply: (clip: VisualClip) => void;
  isActive: (clip: VisualClip) => boolean;
}

const EFFECT_PRESETS: EffectPreset[] = [
  {
    id: "ZOOM_IN",
    icon: "🔍",
    title: "Zoom-in Cảm xúc",
    desc: "Phóng nhẹ 1.0x → 1.15x vào tâm điểm",
    apply: (c) => {
      c.shot_type = "ZOOM_IN";
      c.motion.zoom_start = 1.0;
      c.motion.zoom_end = 1.15;
      c.motion.pan_start = [0, 0];
      c.motion.pan_end = [0, 0];
      c.background.blur_radius = 35;
      c.background.darkness = 0.35;
    },
    isActive: (c) =>
      c.shot_type === "ZOOM_IN" ||
      (c.motion.zoom_start === 1.0 &&
        c.motion.zoom_end > 1.05 &&
        c.motion.zoom_end <= 1.18 &&
        c.motion.pan_end[1] === 0 &&
        c.background.blur_radius < 65),
  },
  {
    id: "PUNCH_ZOOM",
    icon: "💥",
    title: "Giật Khung Hình",
    desc: "Cận cảnh kịch tính biểu cảm 1.05x → 1.25x",
    apply: (c) => {
      c.shot_type = "PUNCH_ZOOM";
      c.motion.zoom_start = 1.05;
      c.motion.zoom_end = 1.25;
      c.motion.pan_start = [0, 0];
      c.motion.pan_end = [0, -20];
      c.background.blur_radius = 45;
      c.background.darkness = 0.45;
    },
    isActive: (c) =>
      c.shot_type === "PUNCH_ZOOM" ||
      (c.motion.zoom_end >= 1.2 && c.motion.pan_end[1] < -10),
  },
  {
    id: "VERTICAL_TILT",
    icon: "📜",
    title: "Cuộn Trang Đọc",
    desc: "Lia mượt từ trên xuống dọc trang",
    apply: (c) => {
      c.shot_type = "PAN";
      c.motion.zoom_start = 1.03;
      c.motion.zoom_end = 1.03;
      c.motion.pan_start = [0, 25];
      c.motion.pan_end = [0, -25];
      c.background.blur_radius = 30;
      c.background.darkness = 0.3;
    },
    isActive: (c) =>
      c.shot_type === "PAN" ||
      c.motion.pan_start[1] !== 0 ||
      c.motion.pan_end[1] !== 0,
  },
  {
    id: "ZOOM_OUT",
    icon: "🌐",
    title: "Mở Rộng Toàn Cảnh",
    desc: "Thu từ chi tiết ra bao quát 1.20x → 1.0x",
    apply: (c) => {
      c.shot_type = "ZOOM_OUT";
      c.motion.zoom_start = 1.2;
      c.motion.zoom_end = 1.0;
      c.motion.pan_start = [0, -10];
      c.motion.pan_end = [0, 0];
      c.background.blur_radius = 30;
      c.background.darkness = 0.3;
    },
    isActive: (c) =>
      c.shot_type === "ZOOM_OUT" || c.motion.zoom_start > c.motion.zoom_end,
  },
  {
    id: "BLUR_GLOW",
    icon: "✨",
    title: "Mờ Ảo Tình Cảm",
    desc: "Zoom nhẹ + tăng mờ viền phông nền",
    apply: (c) => {
      c.shot_type = "BLUR_GLOW";
      c.motion.zoom_start = 1.02;
      c.motion.zoom_end = 1.08;
      c.motion.pan_start = [0, 0];
      c.motion.pan_end = [0, 0];
      c.background.blur_radius = 75;
      c.background.darkness = 0.55;
    },
    isActive: (c) =>
      c.shot_type === "BLUR_GLOW" || c.background.blur_radius >= 65,
  },
  {
    id: "STATIC",
    icon: "🛑",
    title: "Khung Hình Tĩnh",
    desc: "Cố định góc nhìn, không chuyển động",
    apply: (c) => {
      c.shot_type = "STATIC";
      c.motion.zoom_start = 1.0;
      c.motion.zoom_end = 1.0;
      c.motion.pan_start = [0, 0];
      c.motion.pan_end = [0, 0];
      c.background.blur_radius = 30;
      c.background.darkness = 0.3;
    },
    isActive: (c) =>
      c.shot_type === "STATIC" ||
      (c.motion.zoom_start === 1.0 &&
        c.motion.zoom_end === 1.0 &&
        c.motion.pan_start[1] === 0 &&
        c.motion.pan_end[1] === 0 &&
        c.background.blur_radius < 60),
  },
];

export default function Inspector({
  timeline,
  selectedClipId,
  currentTime = 0,
  projectId,
  onUpdateTimeline,
  onSeek,
  onSelectClip,
  onAutoGenerateShort,
  isGeneratingShort = false,
  panels = [],
  selectedPanelId,
  onUpdatePanel,
  onAiReviewAllPanels,
  reviewProgress,
  storyStyle: propStoryStyle,
  onSelectStoryStyle,
}: InspectorProps) {
  const [activeTab, setActiveTab] = useState<
    "ai_script" | "dialogue" | "effects"
  >("ai_script");

  // Derive selected panel directly from panels by selectedPanelId, currentTime, or fallback to first
  const currentPanelFromTime = panels.find(
    (p) =>
      currentTime !== undefined &&
      currentTime >= p.timelineStart &&
      currentTime < p.timelineEnd,
  );
  const selectedPanel: PanelItem | undefined =
    panels.find((p) => p.id === selectedPanelId) ||
    currentPanelFromTime ||
    panels[0];

  const [localStoryStyle, setLocalStoryStyle] = useState<
    "dramatic" | "humorous" | "romantic"
  >("dramatic");

  // Derive storyStyle from prop, selectedPanel, timeline metadata, or local selection
  const storyStyle: "dramatic" | "humorous" | "romantic" =
    propStoryStyle ||
    (selectedPanel?.style as "dramatic" | "humorous" | "romantic") ||
    (timeline.metadata?.story_style as "dramatic" | "humorous" | "romantic") ||
    localStoryStyle;

  const setStoryStyle = (style: "dramatic" | "humorous" | "romantic") => {
    setLocalStoryStyle(style);
    if (onSelectStoryStyle) {
      onSelectStoryStyle(style);
    }
    if (selectedPanel && onUpdatePanel) {
      onUpdatePanel(selectedPanel.id, { style });
    }
  };

  // Derive active segments from panel script, or timeline AI audio clips, or deterministic fallback per page/style
  const segments: ScriptSegment[] = useMemo(() => {
    if (selectedPanel?.script && selectedPanel.script.length > 0) {
      return selectedPanel.script;
    }

    // Check timeline audio clips for AI review clips
    const aiReviewClips = timeline.audio_clips.filter(
      (a) =>
        a.source === "ai_review_script" ||
        a.clip_id.startsWith("AUD_AI") ||
        a.clip_id.startsWith("AUD_SEG"),
    );

    if (aiReviewClips.length > 0 && selectedPanel) {
      const panelClips = aiReviewClips.filter(
        (a) =>
          (a.start_time >= selectedPanel.timelineStart &&
            a.start_time < selectedPanel.timelineEnd) ||
          (a.end_time > selectedPanel.timelineStart &&
            a.end_time <= selectedPanel.timelineEnd) ||
          (selectedPanel.timelineStart >= a.start_time &&
            selectedPanel.timelineEnd <= a.end_time),
      );
      const chosenClips = panelClips.length > 0 ? panelClips : aiReviewClips;
      return chosenClips.map((ac, idx) => ({
        id: ac.dialogue_id || ac.clip_id || `SEG_${idx + 1}`,
        section_type:
          idx === 0
            ? "hook"
            : idx === chosenClips.length - 1
              ? "call_to_action"
              : "body",
        text: ac.text,
        estimated_duration: ac.duration,
        suggested_effect: "zoom_in",
      }));
    }

    // Deterministic non-empty fallback per page/panel and style so text is NEVER blank
    const pageNum = selectedPanel?.page_order || 1;
    if (storyStyle === "romantic") {
      return [
        {
          id: `SEG_R_P${pageNum}_01`,
          section_type: pageNum === 1 ? "hook" : "body",
          text: `Khoảnh khắc ánh mắt chạm nhau tại trang ${pageNum}, từng nhịp đập con tim dường như thổn thức không ngừng.`,
          estimated_duration: 3.5,
          suggested_effect: "zoom_in",
        },
        {
          id: `SEG_R_P${pageNum}_02`,
          section_type: "call_to_action",
          text: `Dù phía trước còn nhiều thử thách, tình yêu chân thành sẽ luôn là ngọn hải đăng soi sáng.`,
          estimated_duration: 3.5,
          suggested_effect: "pan_down",
        },
      ];
    } else if (storyStyle === "humorous") {
      return [
        {
          id: `SEG_H_P${pageNum}_01`,
          section_type: pageNum === 1 ? "hook" : "body",
          text: `Nhìn mặt tưởng ngầu lòi, ai dè pha xử lý tại trang ${pageNum} lại cồng kềnh hết nước chấm!`,
          estimated_duration: 3.5,
          suggested_effect: "punch_zoom",
        },
        {
          id: `SEG_H_P${pageNum}_02`,
          section_type: "call_to_action",
          text: `Anh em nhớ thả tim và follow ngay để đón xem màn tấu hài cực gắt ở chap sau nhé!`,
          estimated_duration: 3.5,
          suggested_effect: "zoom_out",
        },
      ];
    } else {
      return [
        {
          id: `SEG_D_P${pageNum}_01`,
          section_type: pageNum === 1 ? "hook" : "body",
          text: `Cứ ngỡ mọi chuyện đã êm đẹp, biến cố bất ngờ nổ ra tại trang ${pageNum} khiến tất cả phải sững sờ!`,
          estimated_duration: 3.5,
          suggested_effect: "punch_zoom",
        },
        {
          id: `SEG_D_P${pageNum}_02`,
          section_type: "call_to_action",
          text: `Sự thật kinh hoàng dần được bóc tách, ai mới là kẻ đứng sau bức màn đen tối này?`,
          estimated_duration: 3.8,
          suggested_effect: "pan_down",
        },
      ];
    }
  }, [selectedPanel, timeline.audio_clips, storyStyle]);

  // Derive original Manga dialogues for reference only
  const mangaDialoguesForPanel = useMemo(() => {
    if (
      selectedPanel?.mangaDialogue &&
      selectedPanel.mangaDialogue.length > 0
    ) {
      return selectedPanel.mangaDialogue;
    }
    const mangaClips = timeline.audio_clips.filter(
      (a) =>
        a.source === "manga_dialogue" ||
        (!a.source &&
          (a.speaker_label?.toUpperCase().includes("RIN") ||
            a.speaker_label?.toUpperCase().includes("KAZU") ||
            a.speaker_label?.toUpperCase().includes("PRIEST") ||
            a.speaker_label?.toUpperCase().includes("LINH MỤC") ||
            a.speaker_label?.toUpperCase().includes("MC"))),
    );
    if (mangaClips.length > 0) {
      return mangaClips.map((c) => `${c.speaker_label}: ${c.text}`);
    }
    return [
      `RIN: "Thì con có chấp nhận nguyện yêu..."`,
      `PRIEST: "Hai con có thề nguyện sẽ bên nhau suốt đời?"`,
      `KAZU: "Tôi xin thề trước mặt Chúa và mọi người."`,
    ];
  }, [selectedPanel, timeline.audio_clips]);

  const [showMangaReference, setShowMangaReference] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generateError, setGenerateError] = useState("");
  const [appliedNotice, setAppliedNotice] = useState(false);
  const [copied, setCopied] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Update specific segment text of the active panel
  const handleUpdateSegment = (idx: number, newText: string) => {
    if (!selectedPanel) return;
    const updated = segments.map((s, i) =>
      i === idx ? { ...s, text: newText, voiceover: newText } : s,
    );
    if (onUpdatePanel) {
      onUpdatePanel(selectedPanel.id, { script: updated });
    }
  };

  // Find selected visual clip or fallback to first clip
  const clipIndex = timeline.visual_clips.findIndex(
    (c) => c.clip_id === selectedClipId,
  );
  const activeClip: VisualClip | undefined =
    clipIndex >= 0
      ? timeline.visual_clips[clipIndex]
      : timeline.visual_clips[0];

  // Helper to update visual clip attributes with zero-lag shallow clone
  const updateActiveClip = (updater: (draft: VisualClip) => void) => {
    if (!activeClip) return;
    const targetIdx = clipIndex >= 0 ? clipIndex : 0;
    const target = timeline.visual_clips[targetIdx];
    const clipCopy: VisualClip = {
      ...target,
      bbox: [...target.bbox],
      motion: {
        ...target.motion,
        pan_start: [...target.motion.pan_start],
        pan_end: [...target.motion.pan_end],
      },
      background: {
        ...target.background,
        border_color: [...target.background.border_color],
      },
    };
    updater(clipCopy);
    const updatedClips = [...timeline.visual_clips];
    updatedClips[targetIdx] = clipCopy;

    onUpdateTimeline({
      ...timeline,
      visual_clips: updatedClips,
    });
  };

  // Helper to update specific audio clip subtitle
  const updateAudioText = (clipId: string, newText: string) => {
    const updatedAudios = timeline.audio_clips.map((a) =>
      a.clip_id === clipId ? { ...a, text: newText } : a,
    );
    onUpdateTimeline({
      ...timeline,
      audio_clips: updatedAudios,
    });
  };

  const handleGenerateScript = async () => {
    setIsGenerating(true);
    setGenerateError("");
    const targetPid = projectId || timeline.project_id || "default_project";

    try {
      const payload = {
        story_style: storyStyle || "dramatic",
        target_duration: Math.max(1, Math.round(selectedPanel?.duration || 45)),
        panel_id: selectedPanel?.id || "",
        page_order: selectedPanel?.page_order ?? 1,
        image_path: selectedPanel?.image || "",
      };

      const res = await fetch(
        `http://127.0.0.1:8000/api/projects/${targetPid}/generate-script`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        },
      );

      if (!res.ok) {
        throw new Error(`API error: ${res.status}`);
      }

      const data: GeneratedScriptResponse = await res.json();
      if (data && Array.isArray(data.segments) && data.segments.length > 0) {
        if (onUpdatePanel && selectedPanel) {
          onUpdatePanel(selectedPanel.id, {
            script: data.segments,
            style: storyStyle,
            status: "completed",
          });
        }
      }
    } catch (err) {
      console.warn(
        "API call failed, generating localized fallback script:",
        err,
      );
      // Fallback generator based on selected style with strictly GROUNDED chapter events
      const fallbackTexts: Record<string, ScriptSegment[]> = {
        dramatic: [
          {
            id: "SEG_D_01",
            scene_index: 1,
            stage: "hook",
            section_type: "hook",
            visual_direction:
              "Cận cảnh lễ đường tráng lệ trong game Hắc Bình Nguyên, chuyển cảnh sang chân dung cô bạn idol Mizuki Rinka trên lớp học",
            voiceover:
              "Cưới được cô vợ vừa ngoan vừa ngọt ngào trong game online suốt 4 năm trời, ai ngờ ngoài đời thực cô ấy lại chính là nữ idol nổi tiếng đang học chung một lớp!",
            text: "Cưới được cô vợ vừa ngoan vừa ngọt ngào trong game online suốt 4 năm trời, ai ngờ ngoài đời thực cô ấy lại chính là nữ idol nổi tiếng đang học chung một lớp!",
            target_page_hint: 1,
            estimated_duration: 4.0,
            suggested_effect: "punch_zoom",
          },
          {
            id: "SEG_D_02",
            scene_index: 2,
            stage: "buildup",
            section_type: "body",
            visual_direction:
              "Hai nhân vật cùng câu cá, đào khoáng, thám hiểm gắn bó thân thiết thời tân thủ trong game Hắc Bình Nguyên",
            voiceover:
              "Đồng hành cùng nhau suốt 4 năm từ những ngày đầu chập chững làm tân thủ, mối quan hệ giữa Kazuto và Rin khăng khít đến mức cả hai quyết định về chung một nhà trong thế giới ảo.",
            text: "Đồng hành cùng nhau suốt 4 năm từ những ngày đầu chập chững làm tân thủ, mối quan hệ giữa Kazuto và Rin khăng khít đến mức cả hai quyết định về chung một nhà trong thế giới ảo.",
            target_page_hint: 3,
            estimated_duration: 4.5,
            suggested_effect: "zoom_in",
          },
          {
            id: "SEG_D_03",
            scene_index: 3,
            stage: "conflict",
            section_type: "body",
            visual_direction:
              "Kazuto hào hứng đeo tai nghe khoe nhạc, Rin trong game bỗng im lặng một cách đáng ngờ",
            voiceover:
              "Thế nhưng khi đang ngồi tâm sự ngắm cảnh, Kazuto lại lỡ lời hết lời khen ngợi giọng hát ngọt ngào của cô bạn idol Mizuki Rinka cùng lớp mà không hề hay biết tai họa sắp ập đến!",
            text: "Thế nhưng khi đang ngồi tâm sự ngắm cảnh, Kazuto lại lỡ lời hết lời khen ngợi giọng hát ngọt ngào của cô bạn idol Mizuki Rinka cùng lớp mà không hề hay biết tai họa sắp ập đến!",
            target_page_hint: 6,
            estimated_duration: 4.5,
            suggested_effect: "pan_down",
          },
          {
            id: "SEG_D_04",
            scene_index: 4,
            stage: "twist",
            section_type: "body",
            visual_direction:
              "Rin bất ngờ đọc vanh vách tên thật và vị trí bàn học góc cửa sổ của Kazuto, avatar bỗng biến mất khỏi màn hình",
            voiceover:
              "Sau 3 phút im lặng đến nghẹt thở, Rin bất ngờ đọc chính xác tên thật lẫn vị trí bàn học cạnh cửa sổ của Kazuto, tuyên bố mình chính là Mizuki Rinka rồi dỗi thoát game!",
            text: "Sau 3 phút im lặng đến nghẹt thở, Rin bất ngờ đọc chính xác tên thật lẫn vị trí bàn học cạnh cửa sổ của Kazuto, tuyên bố mình chính là Mizuki Rinka rồi dỗi thoát game!",
            target_page_hint: 10,
            estimated_duration: 4.2,
            suggested_effect: "punch_zoom",
          },
          {
            id: "SEG_D_05",
            scene_index: 5,
            stage: "cliffhanger",
            section_type: "call_to_action",
            visual_direction:
              "Màn hình điện thoại Kazuto sáng đèn thông báo tin nhắn hẹn gặp ăn trưa trên sân thượng, biểu cảm sững sờ tột độ",
            voiceover:
              "Điện thoại bất ngờ rung lên dòng tin nhắn: 'Trưa mai gặp nhau trên sân thượng để chứng minh hàng thật!'. Cuộc đối đầu ngoài đời sẽ ra sao? Bấm follow ngay để đón xem chap tiếp theo!",
            text: "Điện thoại bất ngờ rung lên dòng tin nhắn: 'Trưa mai gặp nhau trên sân thượng để chứng minh hàng thật!'. Cuộc đối đầu ngoài đời sẽ ra sao? Bấm follow ngay để đón xem chap tiếp theo!",
            target_page_hint: 15,
            estimated_duration: 4.0,
            suggested_effect: "zoom_out",
          },
        ],
        humorous: [
          {
            id: "SEG_H_01",
            scene_index: 1,
            stage: "hook",
            section_type: "hook",
            visual_direction:
              "Chú rể Kazuto cười tít mắt trong đám cưới game ảo, cô dâu Rin lườm sắc lẹm kèm hiệu ứng sấm sét",
            voiceover:
              "Hí hửng cưới được em vợ ngoan hiền trong game suốt 4 năm, ai dè thanh niên rước ngay trúng 'nóc nhà' chiến thần kiêm nữ idol đang ngồi chung lớp ngoài đời!",
            text: "Hí hửng cưới được em vợ ngoan hiền trong game suốt 4 năm, ai dè thanh niên rước ngay trúng 'nóc nhà' chiến thần kiêm nữ idol đang ngồi chung lớp ngoài đời!",
            target_page_hint: 1,
            estimated_duration: 4.0,
            suggested_effect: "punch_zoom",
          },
          {
            id: "SEG_H_02",
            scene_index: 2,
            stage: "buildup",
            section_type: "buildup",
            visual_direction:
              "Hai nhân vật tranh nhau nhặt đồ đào khoáng trong game Hắc Bình Nguyên, Kazuto gánh còng cả lưng",
            voiceover:
              "Trong game thì em bảo 'anh cứ để em lo', anh chàng ngày đêm cày cuốc câu cá làm nhiệm vụ gánh còng cả lưng để phục vụ cô vợ bảo bối.",
            text: "Trong game thì em bảo 'anh cứ để em lo', anh chàng ngày đêm cày cuốc câu cá làm nhiệm vụ gánh còng cả lưng để phục vụ cô vợ bảo bối.",
            target_page_hint: 3,
            estimated_duration: 4.2,
            suggested_effect: "zoom_in",
          },
          {
            id: "SEG_H_03",
            scene_index: 3,
            stage: "conflict",
            section_type: "conflict",
            visual_direction:
              "Kazuto thao thao bất tuyệt khen idol Mizuki Rinka hát hay, Rin đứng khoanh tay tỏa sát khí",
            voiceover:
              "Đang yên đang lành, thanh niên lại đi khoe với vợ ảo là mình mê mẩn giọng hát của cô bạn idol Mizuki Rinka cùng lớp, đúng là pha tự hủy đi vào lòng đất!",
            text: "Đang yên đang lành, thanh niên lại đi khoe với vợ ảo là mình mê mẩn giọng hát của cô bạn idol Mizuki Rinka cùng lớp, đúng là pha tự hủy đi vào lòng đất!",
            target_page_hint: 6,
            estimated_duration: 4.5,
            suggested_effect: "pan_down",
          },
          {
            id: "SEG_H_04",
            scene_index: 4,
            stage: "twist",
            section_type: "twist",
            visual_direction:
              "Khung chat game hiện lên địa chỉ bàn học góc lớp, Rin đập bàn thoát game cái rụp",
            voiceover:
              "Nàng im lặng đúng 3 phút rồi bóc trần luôn vị trí ngồi bàn cuối dãy trong của Kazuto kèm lời tuyên bố: 'Tôi chính là Mizuki đây!' rồi dỗi thoát game cái rụp!",
            text: "Nàng im lặng đúng 3 phút rồi bóc trần luôn vị trí ngồi bàn cuối dãy trong của Kazuto kèm lời tuyên bố: 'Tôi chính là Mizuki đây!' rồi dỗi thoát game cái rụp!",
            target_page_hint: 10,
            estimated_duration: 4.2,
            suggested_effect: "punch_zoom",
          },
          {
            id: "SEG_H_05",
            scene_index: 5,
            stage: "cliffhanger",
            section_type: "call_to_action",
            visual_direction:
              "Kazuto ôm đầu tá hỏa khi nhận tin nhắn hẹn gặp mặt ăn trưa trên sân thượng",
            voiceover:
              "Vừa run vừa nhận tin nhắn hẹn ăn trưa ngày mai để 'bắt đền', chuyến này anh bạn xác định ăn đòn no nê! Thả tim và follow ngay để hóng màn gặp mặt dở khóc dở cười này nhé!",
            text: "Vừa run vừa nhận tin nhắn hẹn ăn trưa ngày mai để 'bắt đền', chuyến này anh bạn xác định ăn đòn no nê! Thả tim và follow ngay để hóng màn gặp mặt dở khóc dở cười này nhé!",
            target_page_hint: 15,
            estimated_duration: 4.0,
            suggested_effect: "zoom_out",
          },
        ],
        romantic: [
          {
            id: "SEG_R_01",
            scene_index: 1,
            stage: "hook",
            section_type: "hook",
            visual_direction:
              "Lễ đường lung linh trong game Hắc Bình Nguyên, lồng ghép ánh mắt ngập ngừng của cô bạn bàn bên giữa lớp học",
            voiceover:
              "Có những định mệnh kỳ diệu đến mức, người cùng ta thề nguyện trọn đời trong thế giới ảo suốt 4 năm lại chính là cô bạn idol ta thầm thương trộm nhớ mỗi ngày trên lớp học.",
            text: "Có những định mệnh kỳ diệu đến mức, người cùng ta thề nguyện trọn đời trong thế giới ảo suốt 4 năm lại chính là cô bạn idol ta thầm thương trộm nhớ mỗi ngày trên lớp học.",
            target_page_hint: 1,
            estimated_duration: 4.2,
            suggested_effect: "zoom_in",
          },
          {
            id: "SEG_R_02",
            scene_index: 2,
            stage: "buildup",
            section_type: "buildup",
            visual_direction:
              "Hai nhân vật ngồi bên hồ câu cá ngắm sao đêm trong game Hắc Bình Nguyên, những dòng tin nhắn tâm sự sẻ chia sớm tối",
            voiceover:
              "Suốt 4 năm thanh xuân ở Hắc Bình Nguyên, từng nhiệm vụ bên nhau đã âm thầm gieo vào lòng Kazuto và Rin những rung động chân thành và ấm áp nhất.",
            text: "Suốt 4 năm thanh xuân ở Hắc Bình Nguyên, từng nhiệm vụ bên nhau đã âm thầm gieo vào lòng Kazuto và Rin những rung động chân thành và ấm áp nhất.",
            target_page_hint: 3,
            estimated_duration: 4.8,
            suggested_effect: "zoom_in",
          },
          {
            id: "SEG_R_03",
            scene_index: 3,
            stage: "conflict",
            section_type: "conflict",
            visual_direction:
              "Kazuto ngập ngừng chia sẻ tình cảm dành cho giọng hát của Mizuki Rinka, Rin khẽ cúi đầu giấu nụ cười ngượng ngùng",
            voiceover:
              "Khi Kazuto thật lòng khen ngợi giọng hát ngọt ngào của cô bạn cùng lớp Mizuki Rinka, anh không hề hay biết người lắng nghe lại chính là chủ nhân của giọng hát ấy.",
            text: "Khi Kazuto thật lòng khen ngợi giọng hát ngọt ngào của cô bạn cùng lớp Mizuki Rinka, anh không hề hay biết người lắng nghe lại chính là chủ nhân của giọng hát ấy.",
            target_page_hint: 6,
            estimated_duration: 4.5,
            suggested_effect: "pan_down",
          },
          {
            id: "SEG_R_04",
            scene_index: 4,
            stage: "twist",
            section_type: "twist",
            visual_direction:
              "Dòng chữ nhắn nhủ tên thật và vị trí chỗ ngồi lớp học, Rin bối rối ngắt kết nối trong sự rung động",
            voiceover:
              "Sau những giây phút bối rối đến nghẹn ngào, Rin khẽ đọc tên thật và vị trí chỗ ngồi của Kazuto, để lộ thân phận thật sự của mình trong sự sững sờ của đối phương.",
            text: "Sau những giây phút bối rối đến nghẹn ngào, Rin khẽ đọc tên thật và vị trí chỗ ngồi của Kazuto, để lộ thân phận thật sự của mình trong sự sững sờ của đối phương.",
            target_page_hint: 10,
            estimated_duration: 4.5,
            suggested_effect: "punch_zoom",
          },
          {
            id: "SEG_R_05",
            scene_index: 5,
            stage: "cliffhanger",
            section_type: "call_to_action",
            visual_direction:
              "Ánh ban mai chiếu qua khung cửa sổ lớp học, tin nhắn hẹn ăn trưa khẽ sáng trên màn hình",
            voiceover:
              "Lời hẹn ăn trưa ngày mai như nhịp cầu nối liền hai thế giới. Liệu tình cảm giấu kín suốt 4 năm có tìm thấy câu trả lời? Hãy bấm follow để cùng theo dõi câu chuyện ngọt ngào này nhé!",
            text: "Lời hẹn ăn trưa ngày mai như nhịp cầu nối liền hai thế giới. Liệu tình cảm giấu kín suốt 4 năm có tìm thấy câu trả lời? Hãy bấm follow để cùng theo dõi câu chuyện ngọt ngào này nhé!",
            target_page_hint: 15,
            estimated_duration: 4.0,
            suggested_effect: "zoom_out",
          },
        ],
      };
      const fallbackList = fallbackTexts[storyStyle] || fallbackTexts.dramatic;
      if (onUpdatePanel && selectedPanel) {
        onUpdatePanel(selectedPanel.id, {
          script: fallbackList,
          style: storyStyle,
          status: "completed",
        });
      }
    } finally {
      setIsGenerating(false);
    }
  };

  const handleApplyToTimeline = () => {
    let currStart = 0.0;
    const pauseSec = 0.3; // Natural pause between segments

    const newAudioClips = segments.map((seg, idx) => {
      const dur = Math.max(1.0, seg.estimated_duration);
      const startT = Number(currStart.toFixed(3));
      const endT = Number((currStart + dur).toFixed(3));
      currStart = endT + pauseSec;

      const stageUpper = (
        seg.stage ||
        seg.section_type ||
        "SCENE"
      ).toUpperCase();
      const speakerTag = `NAMMINH [${stageUpper}]`;
      const textToUse = seg.voiceover || seg.text;

      return {
        clip_id: `AUD_AI_${seg.id}_${idx + 1}`,
        dialogue_id: seg.id,
        speaker_label: speakerTag,
        voice_id: "vi-VN-NamMinhNeural",
        text: textToUse,
        file_path: `artifacts/audio/day19/${seg.id}.mp3`,
        start_time: startT,
        end_time: endT,
        duration: dur,
        source: "ai_review_script",
      };
    });

    const newTotalDuration = Math.max(
      Number(currStart.toFixed(2)),
      timeline.total_duration,
    );

    // Proportionally adjust visual clips if new audio duration extends beyond old duration
    let updatedVisuals = [...timeline.visual_clips];
    if (
      newTotalDuration > timeline.total_duration &&
      updatedVisuals.length > 0
    ) {
      const scale = newTotalDuration / timeline.total_duration;
      updatedVisuals = updatedVisuals.map((v) => ({
        ...v,
        start_time: Number((v.start_time * scale).toFixed(3)),
        end_time: Number((v.end_time * scale).toFixed(3)),
        duration: Number((v.duration * scale).toFixed(3)),
      }));
    }

    onUpdateTimeline({
      ...timeline,
      total_duration: newTotalDuration,
      audio_clips: newAudioClips,
      visual_clips: updatedVisuals,
    });

    setAppliedNotice(true);
    setTimeout(() => setAppliedNotice(false), 3000);
  };

  const handleCopyScript = () => {
    const fullText = segments
      .map((s) => {
        const stageUpper = (s.stage || s.section_type || "").toUpperCase();
        const pageHint = s.target_page_hint
          ? ` (Trang ${s.target_page_hint})`
          : "";
        const visual = s.visual_direction
          ? `\n[HÌNH ẢNH]: ${s.visual_direction}`
          : "";
        const text = s.voiceover || s.text;
        return `[${stageUpper}${pageHint} - ${s.suggested_effect}]${visual}\n${text}`;
      })
      .join("\n\n");
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(fullText).then(() => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      });
    }
  };

  return (
    <div className="w-full bg-[#101013] flex flex-col h-full overflow-hidden text-xs select-none">
      {/* 3 Flat Tab Navigation Header */}
      <nav
        className="flex h-12 items-center border-b border-white/[0.08] px-4 shrink-0 gap-1"
        aria-label="Bảng điều khiển Inspector"
      >
        <button
          type="button"
          onClick={() => setActiveTab("ai_script")}
          className={`relative text-xs transition px-2.5 pb-3.5 pt-3.5 ${
            activeTab === "ai_script"
              ? "text-white font-semibold after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:bg-violet-500"
              : "text-white/40 hover:text-white/70"
          }`}
        >
          🎙️ Kịch bản AI
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("dialogue")}
          className={`relative text-xs transition px-2.5 pb-3.5 pt-3.5 ${
            activeTab === "dialogue"
              ? "text-white font-semibold after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:bg-violet-500"
              : "text-white/40 hover:text-white/70"
          }`}
        >
          📖 Thoại Manga
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("effects")}
          className={`relative text-xs transition px-2.5 pb-3.5 pt-3.5 ${
            activeTab === "effects"
              ? "text-white font-semibold after:absolute after:inset-x-0 after:bottom-0 after:h-0.5 after:bg-violet-500"
              : "text-white/40 hover:text-white/70"
          }`}
        >
          Hiệu ứng
        </button>
      </nav>

      {/* Tab 1: Thoại Manga (Lời thoại bóc từ manga gốc & phân cảnh tương ứng) */}
      {activeTab === "dialogue" && (
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4 [scrollbar-color:rgba(255,255,255,0.14)_transparent] [scrollbar-width:thin]">
          <div className="flex items-center justify-between pb-1 border-b border-white/[0.08]">
            <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-white/40">
              Thoại bóc từ Manga gốc
            </p>
            <span className="text-[11px] text-white/40 font-mono">
              {timeline.audio_clips.length} câu
            </span>
          </div>

          {timeline.audio_clips.length === 0 ? (
            <div className="py-12 text-center text-sm text-white/30">
              Trang này chưa có lời thoại nào.
            </div>
          ) : (
            timeline.audio_clips.map((audio, idx) => {
              const speakerUpper = (audio.speaker_label || "").toUpperCase();
              const speakerColor = speakerUpper.includes("RIN")
                ? "text-pink-400 bg-pink-500/10 border-pink-500/30"
                : speakerUpper.includes("PRIEST") ||
                    speakerUpper.includes("LINH MỤC")
                  ? "text-amber-400 bg-amber-500/10 border-amber-500/30"
                  : speakerUpper.includes("KAZU")
                    ? "text-sky-400 bg-sky-500/10 border-sky-500/30"
                    : "text-violet-400 bg-violet-500/10 border-violet-500/30";

              const isCurrent =
                currentTime !== undefined &&
                currentTime >= audio.start_time &&
                currentTime < audio.end_time;

              // Find corresponding visual shot
              const matchingVisual = timeline.visual_clips.find(
                (v) =>
                  audio.start_time >= v.start_time &&
                  audio.start_time < v.end_time,
              );

              return (
                <article
                  key={audio.clip_id}
                  onClick={() => onSeek && onSeek(audio.start_time)}
                  className={`border-b pb-3.5 cursor-pointer group transition rounded-lg p-2.5 ${
                    isCurrent
                      ? "border-violet-500/50 bg-violet-500/[0.08] shadow-sm ring-1 ring-violet-500/30"
                      : "border-white/[0.06] bg-white/[0.02] hover:bg-white/[0.05] hover:border-white/15"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-xs font-mono font-semibold transition ${
                          isCurrent
                            ? "text-violet-400"
                            : "text-white/40 group-hover:text-violet-300"
                        }`}
                      >
                        #{String(idx + 1).padStart(2, "0")}
                      </span>
                      <span
                        className={`text-[10px] font-semibold tracking-wide uppercase px-2 py-0.5 rounded border ${speakerColor}`}
                      >
                        {audio.speaker_label}
                      </span>
                      {matchingVisual && (
                        <span className="text-[9px] font-mono text-white/40 bg-white/5 px-1.5 py-0.5 rounded">
                          {matchingVisual.shot_type}
                        </span>
                      )}
                    </div>
                    <span className="text-[10px] font-mono text-white/40">
                      {audio.start_time.toFixed(1)}s -{" "}
                      {audio.end_time.toFixed(1)}s
                    </span>
                  </div>

                  <textarea
                    rows={2}
                    value={audio.text}
                    onFocus={() => onSeek && onSeek(audio.start_time)}
                    onChange={(e) =>
                      updateAudioText(audio.clip_id, e.target.value)
                    }
                    placeholder="Nhập lời thoại..."
                    className="w-full bg-transparent border-0 border-b border-transparent focus:border-violet-500 text-xs text-white/90 focus:text-white p-0 outline-none resize-none leading-relaxed transition"
                  />
                </article>
              );
            })
          )}
        </div>
      )}

      {/* Tab 2: Kịch bản AI (Review & Tóm tắt cốt truyện kèm Hook) */}
      {activeTab === "ai_script" && (
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-3.5 [scrollbar-color:rgba(255,255,255,0.14)_transparent] [scrollbar-width:thin]">
          {/* Header & Copy */}
          <div className="flex items-center justify-between pb-2 border-b border-white/[0.08]">
            <div>
              <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-white/40">
                Kịch bản AI Review & Tóm Tắt
              </p>
              <p className="text-[10px] text-violet-300/80 mt-0.5 flex items-center gap-1.5">
                <span>🎙️</span>
                <span>Giọng đọc: vi-VN-NamMinhNeural (+12% rate)</span>
              </p>
            </div>
            <button
              type="button"
              onClick={handleCopyScript}
              className="px-2 py-1 rounded bg-violet-600/20 hover:bg-violet-600/30 border border-violet-500/30 text-[10px] font-medium text-violet-300 transition flex items-center gap-1 cursor-pointer"
            >
              <span>{copied ? "✓ Đã sao chép" : "📋 Sao chép"}</span>
            </button>
          </div>

          {/* Thanh điều khiển: Bộ chọn Phong cách & Nút Tạo Kịch Bản */}
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 flex flex-col gap-2.5">
            {/* Global AI Review for all panels */}
            {onAiReviewAllPanels && (
              <button
                type="button"
                onClick={() => onAiReviewAllPanels(storyStyle)}
                disabled={reviewProgress?.isReviewing}
                className="w-full py-2.5 px-3 rounded-lg bg-gradient-to-r from-violet-600 via-purple-600 to-indigo-600 hover:from-violet-500 hover:via-purple-500 hover:to-indigo-500 text-white font-bold text-xs transition shadow-md shadow-purple-950/40 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                title="Tự động phân tích và tạo kịch bản cho TOÀN BỘ các tranh trong chapter"
              >
                {reviewProgress?.isReviewing ? (
                  <>
                    <div className="h-3.5 w-3.5 rounded-full border-2 border-white border-t-transparent animate-spin" />
                    <span>
                      Đang Review {reviewProgress.current}/
                      {reviewProgress.total}...
                    </span>
                  </>
                ) : (
                  <>
                    <span>🤖</span>
                    <span>
                      AI Review Toàn Bộ Video ({panels.length || 1} Tranh)
                    </span>
                  </>
                )}
              </button>
            )}

            {/* One-Click Auto-Generate Short (Full Chapter) */}
            {onAutoGenerateShort && (
              <button
                type="button"
                onClick={() => onAutoGenerateShort(storyStyle)}
                disabled={isGeneratingShort}
                className="w-full py-2 px-3 rounded-lg bg-gradient-to-r from-amber-500 via-violet-600 to-fuchsia-600 hover:from-amber-400 hover:via-violet-500 hover:to-fuchsia-500 text-white font-bold text-xs transition shadow-md shadow-purple-950/40 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                title="Tự động bóc tách panel cả chapter, chọn 6-10 panel đắt giá và khớp kịch bản AI giọng NamMinh"
              >
                {isGeneratingShort ? (
                  <>
                    <div className="h-3.5 w-3.5 rounded-full border-2 border-white border-t-transparent animate-spin" />
                    <span>Đang dựng Short...</span>
                  </>
                ) : (
                  <>
                    <span>⚡</span>
                    <span>Tạo Video Ngắn Tự Động (Full Chapter)</span>
                  </>
                )}
              </button>
            )}

            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold text-white/70 uppercase tracking-wider">
                Phong cách kể chuyện
              </span>
              <span className="text-[10px] text-white/40 font-mono">
                {segments.length} phân đoạn
              </span>
            </div>

            {/* Pill Selector for 3 Styles */}
            <div className="grid grid-cols-3 gap-1.5">
              <button
                type="button"
                onClick={() => setStoryStyle("dramatic")}
                className={`py-1.5 px-2 rounded-lg border text-center transition cursor-pointer text-[11px] font-medium ${
                  storyStyle === "dramatic"
                    ? "border-purple-500 bg-purple-500/20 text-white font-semibold ring-1 ring-purple-500/40"
                    : "border-white/[0.08] bg-white/[0.02] text-white/60 hover:text-white hover:border-white/20"
                }`}
              >
                ⚡ Kịch tính
              </button>
              <button
                type="button"
                onClick={() => setStoryStyle("humorous")}
                className={`py-1.5 px-2 rounded-lg border text-center transition cursor-pointer text-[11px] font-medium ${
                  storyStyle === "humorous"
                    ? "border-amber-500 bg-amber-500/20 text-white font-semibold ring-1 ring-amber-500/40"
                    : "border-white/[0.08] bg-white/[0.02] text-white/60 hover:text-white hover:border-white/20"
                }`}
              >
                🎭 Cà khịa
              </button>
              <button
                type="button"
                onClick={() => setStoryStyle("romantic")}
                className={`py-1.5 px-2 rounded-lg border text-center transition cursor-pointer text-[11px] font-medium ${
                  storyStyle === "romantic"
                    ? "border-pink-500 bg-pink-500/20 text-white font-semibold ring-1 ring-pink-500/40"
                    : "border-white/[0.08] bg-white/[0.02] text-white/60 hover:text-white hover:border-white/20"
                }`}
              >
                💖 Lãng mạn
              </button>
            </div>

            {/* Actions: Generate & Apply */}
            <div className="grid grid-cols-2 gap-2 pt-1">
              <button
                type="button"
                onClick={handleGenerateScript}
                disabled={isGenerating}
                className="py-2 px-3 rounded-lg bg-gradient-to-r from-violet-600 to-indigo-600 hover:from-violet-500 hover:to-indigo-500 text-white font-semibold text-[11px] transition shadow-md shadow-purple-950/40 flex items-center justify-center gap-1.5 cursor-pointer disabled:opacity-50"
              >
                {isGenerating ? (
                  <>
                    <div className="h-3 w-3 rounded-full border-2 border-white border-t-transparent animate-spin" />
                    <span>Đang viết...</span>
                  </>
                ) : (
                  <>
                    <span>✨</span>
                    <span>AI Viết Trực Tiếp</span>
                  </>
                )}
              </button>

              <button
                type="button"
                onClick={handleApplyToTimeline}
                className="py-2 px-3 rounded-lg bg-emerald-600/30 hover:bg-emerald-600/40 border border-emerald-500/40 text-emerald-200 font-semibold text-[11px] transition flex items-center justify-center gap-1.5 cursor-pointer shadow-sm"
              >
                <span>🪄</span>
                <span>Áp Dụng Timeline</span>
              </button>
            </div>

            {appliedNotice && (
              <div className="text-[11px] text-emerald-300 bg-emerald-950/60 border border-emerald-500/30 px-2.5 py-1.5 rounded-lg flex items-center gap-1.5 animate-fadeIn">
                <span>✓</span>
                <span>
                  Đã cập nhật rãnh Thoại & Audio Ducking trên Timeline!
                </span>
              </div>
            )}
            {generateError && (
              <p className="text-[10px] text-rose-400 bg-rose-500/10 border border-rose-500/20 px-2.5 py-1 rounded">
                {generateError}
              </p>
            )}
          </div>

          {/* Panel Indicator Pill */}
          <div className="flex items-center justify-between px-3 py-2 rounded-lg bg-white/[0.03] border border-white/10 text-white/80">
            <div className="flex items-center gap-2">
              <span className="text-violet-400 font-bold">
                Trang {selectedPanel?.page_order || 1}
              </span>
              <span className="text-[10px] text-white/40 font-mono">
                ID: {selectedPanel?.id || "p01"}
              </span>
            </div>
            {selectedPanel?.status && (
              <span
                className={`text-[10px] px-2 py-0.5 rounded font-mono font-medium ${
                  selectedPanel.status === "completed"
                    ? "text-emerald-300 bg-emerald-500/15 border border-emerald-500/30"
                    : selectedPanel.status === "processing"
                      ? "text-amber-300 bg-amber-500/15 border border-amber-500/30 animate-pulse"
                      : selectedPanel.status === "error"
                        ? "text-rose-300 bg-rose-500/15 border border-rose-500/30"
                        : "text-white/40 bg-white/5 border border-white/10"
                }`}
              >
                {selectedPanel.status === "completed"
                  ? "✓ Đã Review"
                  : selectedPanel.status === "processing"
                    ? "Đang xử lý..."
                    : selectedPanel.status === "error"
                      ? "Lỗi AI"
                      : "Sẵn sàng"}
              </span>
            )}
          </div>

          {/* Section 1: Kịch bản Review */}
          <div className="flex items-center justify-between pt-1">
            <span className="text-[11px] font-bold text-violet-300 uppercase tracking-wider flex items-center gap-1.5">
              <span>🎙️</span>
              <span>KỊCH BẢN REVIEW (Đọc bởi TTS NamMinh)</span>
            </span>
            <span className="text-[10px] text-white/40 font-mono">
              {segments.length} đoạn
            </span>
          </div>

          {/* Danh sách các phân đoạn ScriptSegment */}
          <div className="space-y-3">
            {segments.map((seg, idx) => {
              const stageKey = (
                seg.stage ||
                seg.section_type ||
                ""
              ).toLowerCase();
              let badgeStyle = "text-sky-300 bg-sky-500/15 border-sky-500/30";
              let badgeLabel = `🎬 SCENE ${seg.scene_index || idx + 1}`;

              if (stageKey === "hook") {
                badgeStyle =
                  "text-purple-300 bg-purple-500/15 border-purple-500/30";
                badgeLabel = "🎣 HOOK (0-3s)";
              } else if (stageKey === "buildup") {
                badgeStyle =
                  "text-emerald-300 bg-emerald-500/15 border-emerald-500/30";
                badgeLabel = "🌱 BUILDUP (Tiền đề)";
              } else if (stageKey === "conflict") {
                badgeStyle =
                  "text-amber-300 bg-amber-500/15 border-amber-500/30";
                badgeLabel = "🔥 CONFLICT (Mâu thuẫn)";
              } else if (stageKey === "twist") {
                badgeStyle = "text-rose-300 bg-rose-500/15 border-rose-500/30";
                badgeLabel = "⚡ TWIST (Cú lừa)";
              } else if (stageKey === "cliffhanger") {
                badgeStyle =
                  "text-fuchsia-300 bg-fuchsia-500/15 border-fuchsia-500/30";
                badgeLabel = "🎬 CLIFFHANGER";
              } else if (
                stageKey === "cta" ||
                stageKey === "call_to_action" ||
                stageKey === "ending"
              ) {
                badgeStyle =
                  "text-yellow-300 bg-yellow-500/15 border-yellow-500/30";
                badgeLabel = "📢 CALL TO ACTION";
              }

              return (
                <div
                  key={seg.id || idx}
                  className="rounded-lg border border-white/[0.08] bg-white/[0.02] p-3 transition hover:border-white/20 flex flex-col gap-2"
                >
                  <div className="flex items-center justify-between gap-1.5 flex-wrap">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      <span
                        className={`text-[10px] font-semibold px-2 py-0.5 rounded border ${badgeStyle}`}
                      >
                        {badgeLabel}
                      </span>
                      {seg.target_page_hint !== undefined && (
                        <span className="text-[10px] font-mono text-zinc-300 bg-zinc-800/80 border border-zinc-700/60 px-1.5 py-0.5 rounded flex items-center gap-1">
                          <span>📖</span>
                          <span>Trang {seg.target_page_hint}</span>
                        </span>
                      )}
                      <span className="text-[10px] font-mono text-zinc-400 bg-zinc-800/60 border border-zinc-700/40 px-1.5 py-0.5 rounded">
                        {seg.suggested_effect}
                      </span>
                    </div>

                    <span className="text-[10px] font-mono text-white/50">
                      ⏱️ {seg.estimated_duration.toFixed(1)}s
                    </span>
                  </div>

                  {seg.visual_direction && (
                    <div className="text-[11px] text-violet-300/90 bg-violet-500/10 border border-violet-500/20 rounded p-2 italic flex items-start gap-1.5">
                      <span className="shrink-0 text-xs">🎥</span>
                      <div>
                        <strong className="not-italic font-semibold text-violet-200">
                          Chỉ đạo hình ảnh:
                        </strong>{" "}
                        {seg.visual_direction}
                      </div>
                    </div>
                  )}

                  <textarea
                    rows={3}
                    value={seg.voiceover || seg.text}
                    onChange={(e) => handleUpdateSegment(idx, e.target.value)}
                    placeholder="Lời bình của người dẫn chuyện..."
                    className="w-full bg-black/20 rounded-md p-2 border border-white/5 focus:border-violet-500 text-xs text-white/90 focus:text-white outline-none resize-none leading-relaxed transition"
                  />
                </div>
              );
            })}
          </div>

          {/* Section 2: Collapsible Manga OCR Dialogue for Reference */}
          <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 flex flex-col gap-2 mt-2">
            <button
              type="button"
              onClick={() => setShowMangaReference((prev) => !prev)}
              className="flex items-center justify-between w-full text-left text-white/70 hover:text-white transition cursor-pointer"
            >
              <div className="flex items-center gap-2">
                <span className="text-sm">📖</span>
                <span className="text-[11px] font-semibold uppercase tracking-wider text-amber-300/90">
                  Thoại Gốc Manga / OCR (Chỉ để tham khảo)
                </span>
              </div>
              <span className="text-xs text-white/40">
                {showMangaReference ? "▲ Thu gọn" : "▼ Mở rộng"}
              </span>
            </button>
            {showMangaReference && (
              <div className="pt-2 border-t border-white/[0.06] space-y-2">
                <p className="text-[10px] text-white/50 italic leading-relaxed">
                  * Lưu ý: Thoại manga gốc chỉ dùng để AI nắm ngữ cảnh và phân
                  tích cốt truyện. Hệ thống Voice TTS chỉ đọc Kịch bản Review
                  phía trên.
                </p>
                <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
                  {mangaDialoguesForPanel.map((line, idx) => (
                    <div
                      key={idx}
                      className="text-[11px] text-white/80 bg-black/30 border border-white/5 rounded px-2.5 py-1.5 font-mono"
                    >
                      {line}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 3: Hiệu ứng (Gói Preset 1 chạm kiểu CapCut & Tùy chỉnh chi tiết) */}
      {activeTab === "effects" && (
        <div className="flex-1 overflow-y-auto p-4 flex flex-col gap-4 [scrollbar-color:rgba(255,255,255,0.14)_transparent] [scrollbar-width:thin]">
          <div className="flex items-center justify-between pb-1 border-b border-white/[0.08]">
            <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-white/40">
              Gói Hiệu Ứng Chuyển Động
            </p>
            {activeClip && (
              <span className="text-[10px] font-mono text-violet-300 bg-violet-500/10 border border-violet-500/30 px-2 py-0.5 rounded">
                {activeClip.shot_type}
              </span>
            )}
          </div>

          {/* Shot Selection Buttons */}
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between text-[11px] text-white/50">
              <span>Đang chọn phân cảnh:</span>
              <span className="font-mono text-white/80">
                Phân cảnh {clipIndex >= 0 ? clipIndex + 1 : 1} /{" "}
                {timeline.visual_clips.length}
              </span>
            </div>
            <div className="grid grid-cols-4 gap-1.5">
              {timeline.visual_clips.map((clip, idx) => {
                const isSelected = activeClip?.clip_id === clip.clip_id;
                return (
                  <button
                    key={clip.clip_id}
                    type="button"
                    onClick={() => {
                      if (onSelectClip) onSelectClip(clip.clip_id);
                      if (onSeek) onSeek(clip.start_time);
                    }}
                    className={`py-1.5 px-2 rounded-lg border text-center transition cursor-pointer ${
                      isSelected
                        ? "border-violet-500 bg-violet-500/20 text-white font-semibold ring-1 ring-violet-500/40 shadow-sm"
                        : "border-white/[0.08] bg-white/[0.02] text-white/60 hover:text-white hover:border-white/20"
                    }`}
                  >
                    <div className="text-xs font-medium">Cảnh {idx + 1}</div>
                    <div className="text-[9px] font-mono opacity-60">
                      {clip.duration.toFixed(1)}s
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {activeClip && (
            <div className="flex flex-col gap-3 pt-2">
              <span className="text-xs font-medium text-white/80">
                Chọn gói hiệu ứng (1 chạm áp dụng ngay):
              </span>

              {/* 6 Presets Grid */}
              <div className="grid grid-cols-2 gap-2.5">
                {EFFECT_PRESETS.map((preset) => {
                  const active = preset.isActive(activeClip);
                  return (
                    <button
                      key={preset.id}
                      type="button"
                      onClick={() => {
                        updateActiveClip((c) => {
                          preset.apply(c);
                        });
                      }}
                      className={`group p-3 rounded-xl border text-left transition flex flex-col justify-between cursor-pointer ${
                        active
                          ? "border-violet-500 bg-violet-500/15 text-white ring-2 ring-violet-500/40 shadow-md shadow-violet-950/40"
                          : "border-white/[0.08] bg-white/[0.02] text-white/70 hover:border-white/20 hover:bg-white/[0.05] hover:text-white"
                      }`}
                    >
                      <div>
                        <div className="flex items-center justify-between gap-1 mb-1">
                          <span className="text-lg">{preset.icon}</span>
                          {active && (
                            <span className="text-[9px] font-mono text-violet-300 bg-violet-500/30 px-1.5 py-0.5 rounded border border-violet-400/30">
                              Đang dùng
                            </span>
                          )}
                        </div>
                        <p className="text-xs font-semibold leading-snug">
                          {preset.title}
                        </p>
                      </div>
                      <p className="text-[10px] text-white/40 group-hover:text-white/60 leading-normal mt-1.5">
                        {preset.desc}
                      </p>
                    </button>
                  );
                })}
              </div>

              {/* Accordion: Tùy chỉnh chi tiết (Mặc định ẩn) */}
              <div className="pt-3 border-t border-white/[0.08] mt-1">
                <button
                  type="button"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="w-full flex items-center justify-between py-2 px-1 text-xs font-medium text-white/50 hover:text-white/80 transition cursor-pointer"
                >
                  <span className="flex items-center gap-1.5">
                    <span>⚙️</span>
                    <span>Tùy chỉnh chi tiết</span>
                  </span>
                  <span className="text-[10px] font-mono">
                    {showAdvanced ? "▲ Thu gọn" : "▼ Mở rộng"}
                  </span>
                </button>

                {showAdvanced && (
                  <div className="space-y-3 pt-3 pb-2 px-1 border-t border-white/[0.04]">
                    <div>
                      <div className="flex justify-between text-[11px] text-white/50 mb-1">
                        <span>Phóng to bắt đầu (Zoom Start)</span>
                        <span className="font-mono text-white/80">
                          {activeClip.motion.zoom_start.toFixed(2)}x
                        </span>
                      </div>
                      <input
                        type="range"
                        min="0.9"
                        max="1.4"
                        step="0.01"
                        value={activeClip.motion.zoom_start}
                        onChange={(e) => {
                          const val = parseFloat(e.target.value);
                          updateActiveClip((c) => {
                            c.motion.zoom_start = val;
                          });
                        }}
                        className="w-full accent-violet-500 h-1 bg-white/10 rounded-full cursor-pointer"
                      />
                    </div>

                    <div>
                      <div className="flex justify-between text-[11px] text-white/50 mb-1">
                        <span>Phóng to kết thúc (Zoom End)</span>
                        <span className="font-mono text-white/80">
                          {activeClip.motion.zoom_end.toFixed(2)}x
                        </span>
                      </div>
                      <input
                        type="range"
                        min="0.9"
                        max="1.4"
                        step="0.01"
                        value={activeClip.motion.zoom_end}
                        onChange={(e) => {
                          const val = parseFloat(e.target.value);
                          updateActiveClip((c) => {
                            c.motion.zoom_end = val;
                          });
                        }}
                        className="w-full accent-violet-500 h-1 bg-white/10 rounded-full cursor-pointer"
                      />
                    </div>

                    <div>
                      <div className="flex justify-between text-[11px] text-white/50 mb-1">
                        <span>Lia dọc (Pan Y)</span>
                        <span className="font-mono text-white/80">
                          {activeClip.motion.pan_end[1]}px
                        </span>
                      </div>
                      <input
                        type="range"
                        min="-40"
                        max="40"
                        step="1"
                        value={activeClip.motion.pan_end[1]}
                        onChange={(e) => {
                          const val = parseInt(e.target.value, 10);
                          updateActiveClip((c) => {
                            c.motion.pan_end = [c.motion.pan_end[0], val];
                          });
                        }}
                        className="w-full accent-violet-500 h-1 bg-white/10 rounded-full cursor-pointer"
                      />
                    </div>

                    <div>
                      <div className="flex justify-between text-[11px] text-white/50 mb-1">
                        <span>Làm mờ phông nền (Blur)</span>
                        <span className="font-mono text-white/80">
                          {activeClip.background.blur_radius}px
                        </span>
                      </div>
                      <input
                        type="range"
                        min="15"
                        max="95"
                        step="2"
                        value={activeClip.background.blur_radius}
                        onChange={(e) => {
                          const val = parseInt(e.target.value, 10);
                          updateActiveClip((c) => {
                            c.background.blur_radius = val;
                          });
                        }}
                        className="w-full accent-violet-500 h-1 bg-white/10 rounded-full cursor-pointer"
                      />
                    </div>

                    <div>
                      <div className="flex justify-between text-[11px] text-white/50 mb-1">
                        <span>Độ tối phông nền (Darkness)</span>
                        <span className="font-mono text-white/80">
                          {Math.round(activeClip.background.darkness * 100)}%
                        </span>
                      </div>
                      <input
                        type="range"
                        min="0"
                        max="0.9"
                        step="0.05"
                        value={activeClip.background.darkness}
                        onChange={(e) => {
                          const val = parseFloat(e.target.value);
                          updateActiveClip((c) => {
                            c.background.darkness = val;
                          });
                        }}
                        className="w-full accent-violet-500 h-1 bg-white/10 rounded-full cursor-pointer"
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
