import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AbsoluteFill,
  CalculateMetadataFunction,
  cancelRender,
  continueRender,
  delayRender,
  getStaticFiles,
  OffthreadVideo,
  Sequence,
  staticFile,
  useVideoConfig,
  watchStaticFile,
} from "remotion";
import { z } from "zod";
import SubtitlePage from "./SubtitlePage";
import { getVideoMetadata } from "@remotion/media-utils";
import { loadFont } from "../load-font";
import { NoCaptionFile } from "./NoCaptionFile";
import { Caption, createTikTokStyleCaptions } from "@remotion/captions";

export type SubtitleProp = {
  startInSeconds: number;
  text: string;
};

export const captionedVideoSchema = z.object({
  src: z.string(),
});

export const calculateCaptionedVideoMetadata: CalculateMetadataFunction<
  z.infer<typeof captionedVideoSchema>
> = async ({ props }) => {
  const fps = 30;
  const metadata = await getVideoMetadata(props.src);

  return {
    fps,
    durationInFrames: Math.floor(metadata.durationInSeconds * fps),
  };
};

const getFileExists = (file: string) => {
  const files = getStaticFiles();
  const fileExists = files.find((f) => {
    return f.src === file;
  });
  return Boolean(fileExists);
};

// How many captions should be displayed at a time?
// Try out:
// - 1500 to display a lot of words at a time
// - 200 to only display 1 word at a time
const SWITCH_CAPTIONS_EVERY_MS = 1200;

export const CaptionedVideo: React.FC<{
  src: string;
}> = ({ src }) => {
  const [subtitles, setSubtitles] = useState<Caption[]>([]);
  const [handle, setHandle] = useState<string | null>(null);
  const { fps } = useVideoConfig();

  const subtitlesFile = src
    .replace(/.mp4$/, ".json")
    .replace(/.mkv$/, ".json")
    .replace(/.mov$/, ".json")
    .replace(/.webm$/, ".json");

  const fetchSubtitles = useCallback(async () => {
    if (!handle) return;
    
    try {
      await loadFont();
      
      // Check if subtitles file exists first
      if (!getFileExists(subtitlesFile)) {
        console.log(`No subtitles file found: ${subtitlesFile}`);
        setSubtitles([]);
        continueRender(handle);
        return;
      }
      
      const res = await fetch(subtitlesFile);
      if (!res.ok) {
        throw new Error(`Failed to fetch subtitles: ${res.status}`);
      }
      
      const data = (await res.json()) as Caption[];
      setSubtitles(data);
      continueRender(handle);
    } catch (e) {
      console.error('Error loading subtitles:', e);
      setSubtitles([]);
      continueRender(handle);
    }
  }, [handle, subtitlesFile]);

  useEffect(() => {
    const renderHandle = delayRender("wait video", {
      timeoutInMilliseconds: 700000,
      retries: 3
    });
    setHandle(renderHandle);

    return () => {
      if (renderHandle) {
        continueRender(renderHandle);
      }
    };
  }, []);

  useEffect(() => {
    if (handle) {
      fetchSubtitles();

      const c = watchStaticFile(subtitlesFile, () => {
        fetchSubtitles();
      });

      return () => {
        c.cancel();
      };
    }
  }, [fetchSubtitles, handle, subtitlesFile]);

  const { pages } = useMemo(() => {
    return createTikTokStyleCaptions({
      combineTokensWithinMilliseconds: SWITCH_CAPTIONS_EVERY_MS,
      captions: subtitles ?? [],
    });
  }, [subtitles]);
  const getLogo = useCallback(() => {
    return staticFile("img/logo.jpg");
  }, []);
  const getLeonLogo = useCallback(() => {
    return staticFile("img/leon.png");
  }, []);
  const getMileiLogo = useCallback(() => {
    return staticFile("img/mileimotosierra.png");
  }, []);
  return (
    <AbsoluteFill className="bg-amber-400">
      <AbsoluteFill className="flex flex-col items-center justify-center">
        <img 
          src={getLogo()} 
          alt="logo" 
          className="z-50 absolute w-64 left-[50rem] bottom-[103rem] rounded-2xl"
        />
        <img 
          src={getLeonLogo()} 
          alt="logo" 
          className="z-10 absolute w-full h-full"
          style={{ objectFit: 'cover' }}
        />
        <img 
          src={getMileiLogo()} 
          alt="logo" 
          className="z-50 absolute w-2xl right-[35rem] top-[80rem]"
        />
        <OffthreadVideo
          style={{
            objectFit: "cover",
          }}
          className="z-40 w-4xl rounded-3xl"
          src={src}
        />
      </AbsoluteFill>
      {pages.map((page, index) => {
        const nextPage = pages[index + 1] ?? null;
        const subtitleStartFrame = (page.startMs / 1000) * fps;
        const subtitleEndFrame = Math.min(
          nextPage ? (nextPage.startMs / 1000) * fps : Infinity,
          subtitleStartFrame + SWITCH_CAPTIONS_EVERY_MS,
        );
        const durationInFrames = subtitleEndFrame - subtitleStartFrame;
        if (durationInFrames <= 0) {
          return null;
        }

        return (
          <Sequence
            key={index}
            from={subtitleStartFrame}
            durationInFrames={durationInFrames}
            className="z-50"
          >
            <SubtitlePage key={index} page={page} />
          </Sequence>
        );
      })}
      {getFileExists(subtitlesFile) ? null : <NoCaptionFile />}
    </AbsoluteFill>
  );
};
