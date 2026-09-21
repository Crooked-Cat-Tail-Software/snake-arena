// Client-side Snake game logic and rendering. The server never sees any
// of this — only the final score, once, at game over (see product-spec.md
// section 5.1/5.2).
const GRID_SIZE = 20;
const CELL_PX = 20;
const TICK_MS = 120;

export class SnakeGame {
  constructor(canvas, { onScoreChange, onGameOver } = {}) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.onScoreChange = onScoreChange || (() => {});
    this.onGameOver = onGameOver || (() => {});
    this._timer = null;
    this._reset();
  }

  _reset() {
    const start = Math.floor(GRID_SIZE / 2);
    this.snake = [
      { x: start - 1, y: start },
      { x: start - 2, y: start },
      { x: start - 3, y: start },
    ];
    this.direction = { x: 1, y: 0 };
    this.pendingDirection = null;
    this.score = 0;
    this.gameOver = false;
    this.food = this._spawnFood();
  }

  start() {
    this._reset();
    this._draw();
    this.onScoreChange(this.score);
    if (this._timer) clearInterval(this._timer);
    this._timer = setInterval(() => this._tick(), TICK_MS);
  }

  stop() {
    if (this._timer) clearInterval(this._timer);
    this._timer = null;
  }

  setDirection(dx, dy) {
    // Ignore a reversal directly into the snake's own neck.
    if (dx === -this.direction.x && dy === -this.direction.y) return;
    this.pendingDirection = { x: dx, y: dy };
  }

  _spawnFood() {
    const occupied = new Set(this.snake.map((s) => `${s.x},${s.y}`));
    let cell;
    do {
      cell = {
        x: Math.floor(Math.random() * GRID_SIZE),
        y: Math.floor(Math.random() * GRID_SIZE),
      };
    } while (occupied.has(`${cell.x},${cell.y}`));
    return cell;
  }

  _tick() {
    if (this.gameOver) return;

    if (this.pendingDirection) {
      this.direction = this.pendingDirection;
      this.pendingDirection = null;
    }

    const head = this.snake[0];
    const newHead = {
      x: head.x + this.direction.x,
      y: head.y + this.direction.y,
    };

    const hitWall =
      newHead.x < 0 ||
      newHead.x >= GRID_SIZE ||
      newHead.y < 0 ||
      newHead.y >= GRID_SIZE;
    const hitSelf = this.snake.some(
      (seg) => seg.x === newHead.x && seg.y === newHead.y
    );

    if (hitWall || hitSelf) {
      this.gameOver = true;
      this.stop();
      this.onGameOver(this.score);
      return;
    }

    this.snake.unshift(newHead);

    if (newHead.x === this.food.x && newHead.y === this.food.y) {
      this.score += 1;
      this.onScoreChange(this.score);
      this.food = this._spawnFood();
    } else {
      this.snake.pop();
    }

    this._draw();
  }

  _draw() {
    const ctx = this.ctx;
    ctx.fillStyle = "#0d1117";
    ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);

    this.snake.forEach((seg, i) => {
      ctx.fillStyle = i === 0 ? "#56d364" : "#3fb950";
      ctx.fillRect(seg.x * CELL_PX + 1, seg.y * CELL_PX + 1, CELL_PX - 2, CELL_PX - 2);
    });

    ctx.fillStyle = "#f85149";
    ctx.fillRect(
      this.food.x * CELL_PX + 1,
      this.food.y * CELL_PX + 1,
      CELL_PX - 2,
      CELL_PX - 2
    );
  }
}
