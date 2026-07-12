export default function RequestButtons({ onRequest }) {
  return (
    <div className="request-actions" aria-label="Client requests">
      <button 
        id="request-a-button" 
        className="request-action-button" 
        type="button" 
        aria-label="Send request A"
        onClick={() => onRequest('a')}
      >
        A
      </button>
      <button 
        id="request-b-button" 
        className="request-action-button" 
        type="button" 
        aria-label="Send request B"
        onClick={() => onRequest('b')}
      >
        B
      </button>
      <button 
        id="request-x-button" 
        className="request-action-button" 
        type="button" 
        aria-label="Send request X"
        onClick={() => onRequest('x')}
      >
        X
      </button>
      <button 
        id="request-y-button" 
        className="request-action-button" 
        type="button" 
        aria-label="Send request Y"
        onClick={() => onRequest('y')}
      >
        Y
      </button>
    </div>
  );
}
