export type HealthResponse = {
  status: "ok" | "degraded";
  database: {
    status: "ok" | "error";
  };
  redis: {
    status: "ok" | "error";
  };
};
