namespace IParkingYoloInfer;

public sealed record DetectionResult(
    float X1, float Y1, float X2, float Y2,
    float Confidence,
    int   ClassIndex,
    string ClassName)
{
    public float Width  => X2 - X1;
    public float Height => Y2 - Y1;
    public System.Drawing.RectangleF Rect => new(X1, Y1, Width, Height);

    public override string ToString() =>
        $"[{ClassName}] {Confidence:P0}  ({X1:F0},{Y1:F0})-({X2:F0},{Y2:F0})";
}
