import { ThreeDot } from "react-loading-indicators";
function Loading() {
  return (
    <div className="d-flex align-items-center">
    
    <p className="text-secondary mb-0 me-2">
      Thinking
    </p>
    <ThreeDot color="#dddddd" size="small" text="" textColor="" />

    </div>
);
}

export default Loading;