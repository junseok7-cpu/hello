import React from "react";
import { Composition } from "remotion";
import { Milmyeon } from "./milmyeon/Milmyeon";
import timing from "./milmyeon/timing.json";
import { Mate } from "./mate/Mate";
import mateTiming from "./mate/timing.json";

export const RemotionRoot: React.FC = () => (
  <>
    <Composition
      id="Milmyeon"
      component={Milmyeon}
      durationInFrames={timing.total}
      fps={timing.fps}
      width={1080}
      height={1920}
    />
    <Composition
      id="Mate"
      component={Mate}
      durationInFrames={mateTiming.total}
      fps={mateTiming.fps}
      width={1080}
      height={1920}
    />
  </>
);
