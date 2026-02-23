-- Enable Row Level Security on the logentry table
ALTER TABLE public.logentry ENABLE ROW LEVEL SECURITY;

-- Create policy for all operations (SELECT, INSERT, UPDATE, DELETE)
-- This allows users to access and modify only their own log entries.
-- We cast auth.uid() to text since logentry.user_id is a character varying column.
CREATE POLICY "Users can only access their own log entries"
ON public.logentry
FOR ALL
USING (
  user_id = (select auth.uid())::text
  OR user_id = (select current_setting('request.jwt.claim.sub', true))
);
