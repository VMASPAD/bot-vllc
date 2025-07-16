import { continueRender, delayRender, staticFile } from "remotion";

export const TheBoldFont = `CalSans`;

let loaded = false;

export const loadFont = async (): Promise<void> => {
  if (loaded) {
    return Promise.resolve();
  }

  const waitForFont = delayRender("wait font", {timeoutInMilliseconds: 50000, retries: 5});

  loaded = true;

  const font = new FontFace(
    TheBoldFont,
    `url('${staticFile("CalSans-Regular.ttf")}') format('truetype')`,
  );

  await font.load();
  document.fonts.add(font);

  continueRender(waitForFont);
};
