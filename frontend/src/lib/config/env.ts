type FrontendEnv = {
  apiBaseUrl: string;
};

export const env: FrontendEnv = {
  apiBaseUrl: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
};
